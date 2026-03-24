"""Core MoA, Expert Panel, Cascade, and Debate engine."""

import asyncio
import json
import time
from typing import List, Optional, Dict, Any

from litellm import acompletion

from .config import (
    MODEL_TIMEOUT_SECONDS, AGGREGATOR_TIMEOUT_SECONDS, PROVIDER_CONCURRENCY,
)
from .budget import check_budget, record_spend
from .models import (
    ModelConfig, Tier, QueryCost, ReviewerRole,
    TIERS, REVIEWER_ROLES, get_aggregator,
    CLAUDE_HAIKU, CASCADE_CONFIDENCE_PROMPT,
    AdaptiveTier, ADAPTIVE_TIERS, CLASSIFIER_MODEL,
)
from .prompts import (
    MOA_AGGREGATOR_SYSTEM, DEBATE_ROUND_SYSTEM, DEBATE_JUDGE_SYSTEM,
    CODE_REVIEW_AGGREGATOR, format_proposals, format_review_findings,
    CLASSIFY_QUERY_PROMPT, DISAGREEMENT_SYNTHESIS_PROMPT, CONSENSUS_AGGREGATOR_PROMPT,
)


# ── Per-provider rate limiting ─────────────────────────────────────────────────

_provider_semaphores: Dict[str, asyncio.Semaphore] = {}


def _get_semaphore(provider: str) -> asyncio.Semaphore:
    """Get or create a per-provider concurrency semaphore."""
    if provider not in _provider_semaphores:
        limit = PROVIDER_CONCURRENCY.get(provider, 5)
        _provider_semaphores[provider] = asyncio.Semaphore(limit)
    return _provider_semaphores[provider]


def _check_budget_or_raise():
    """Check daily budget and raise if exceeded."""
    allowed, spend, cap = check_budget()
    if not allowed:
        raise RuntimeError(
            f"Daily budget exceeded: ${spend:.4f} / ${cap:.2f}. "
            f"Increase MAX_DAILY_SPEND_USD in config or wait until tomorrow."
        )


# ── Real cost calculation ──────────────────────────────────────────────────────

def calculate_real_cost(model: ModelConfig, input_tokens: int, output_tokens: int) -> float:
    """Calculate actual cost from real token counts."""
    return (
        model.input_cost_per_mtok * input_tokens / 1_000_000
        + model.output_cost_per_mtok * output_tokens / 1_000_000
    )


# ── Low-level model call with timeout ─────────────────────────────────────────

async def call_model(
    model: ModelConfig,
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Call a single model via LiteLLM with timeout, retry, and graceful failure.

    Returns dict with 'content', 'input_tokens', 'output_tokens', 'model',
    'provider', 'cost_usd', 'latency_s' or None on total failure.
    """
    temp = temperature if temperature is not None else model.temperature
    max_tok = max_tokens or model.max_tokens
    call_timeout = timeout or MODEL_TIMEOUT_SECONDS

    start = time.monotonic()
    last_error = None

    for attempt in range(3):
        try:
            sem = _get_semaphore(model.provider)
            async with sem:
                resp = await asyncio.wait_for(
                    acompletion(
                        model=model.name,
                        messages=messages,
                        temperature=temp,
                        max_tokens=max_tok,
                    ),
                    timeout=call_timeout,
                )
            elapsed = time.monotonic() - start
            usage = resp.get("usage", {})
            input_tok = usage.get("prompt_tokens", 0)
            output_tok = usage.get("completion_tokens", 0)

            return {
                "content": resp.choices[0].message.content,
                "input_tokens": input_tok,
                "output_tokens": output_tok,
                "cost_usd": calculate_real_cost(model, input_tok, output_tok),
                "model": model.name,
                "provider": model.provider,
                "latency_s": round(elapsed, 2),
            }
        except asyncio.TimeoutError:
            last_error = f"timeout ({call_timeout}s)"
            break  # Don't retry timeouts
        except Exception as e:
            last_error = str(e)[:100]
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

    # Return failure info (not None) so we can report what happened
    return None


def _update_cost(cost: QueryCost, result: Dict, model: ModelConfig = None, is_aggregator: bool = False):
    """Update cost tracker with a model call result."""
    if is_aggregator:
        cost.aggregator_calls += 1
    else:
        cost.proposer_calls += 1
    cost.total_input_tokens += result["input_tokens"]
    cost.total_output_tokens += result["output_tokens"]
    cost.estimated_cost_usd += result.get("cost_usd", 0.0)
    cost.models_used.append(result["model"])


# ══════════════════════════════════════════════════════════════════════════════
#  MIXTURE OF AGENTS — standard 2-layer pattern
# ══════════════════════════════════════════════════════════════════════════════

async def run_moa(
    query: str,
    tier_name: str = "lite",
) -> Dict[str, Any]:
    """Run a 2-layer Mixture-of-Agents query.

    Layer 1: Parallel proposers generate independent responses.
    Layer 2: Aggregator synthesizes proposals into one high-quality response.
    """
    _check_budget_or_raise()

    tier = TIERS.get(tier_name)
    if not tier:
        raise ValueError(f"Unknown tier: {tier_name}. Options: {list(TIERS.keys())}")

    available = tier.available_proposers
    if not available:
        raise RuntimeError(
            f"No proposers available for tier '{tier_name}'. "
            f"Set API keys: {list(set(m.env_key for m in tier.proposers))}"
        )

    cost = QueryCost(tier=tier_name)
    start = time.monotonic()
    user_msg = [{"role": "user", "content": query}]

    # ── Layer 1: Parallel proposers ────────────────────────────────────────
    tasks = [call_model(m, user_msg) for m in available]
    results = await asyncio.gather(*tasks)

    proposals = []
    model_names = []
    model_status = {}

    for model, r in zip(available, results):
        short_name = model.name.split("/")[-1] if "/" in model.name else model.name
        if r:
            proposals.append(r["content"])
            model_names.append(r["provider"])
            _update_cost(cost, r)
            model_status[short_name] = f"✅ {r['latency_s']}s"
        else:
            model_status[short_name] = "❌ failed"

    if not proposals:
        raise RuntimeError("All proposers failed. Check API keys and network.")

    # ── Flash tier: no aggregation ─────────────────────────────────────────
    if not tier.aggregator:
        elapsed = int((time.monotonic() - start) * 1000)
        return {
            "response": proposals[0],
            "proposals": proposals,
            "model_names": model_names,
            "model_status": model_status,
            "cost": cost,
            "latency_ms": elapsed,
        }

    # ── Layer 2: Aggregation ───────────────────────────────────────────────
    prefer_premium = tier_name in ("ultra",)
    aggregator = tier.aggregator if tier.aggregator.available else get_aggregator(prefer_premium)

    if not aggregator:
        elapsed = int((time.monotonic() - start) * 1000)
        return {
            "response": proposals[0], "proposals": proposals,
            "model_names": model_names, "model_status": model_status,
            "cost": cost, "latency_ms": elapsed,
            "warning": "No aggregator available — returning first proposal",
        }

    system_prompt = MOA_AGGREGATOR_SYSTEM.format(
        proposals=format_proposals(proposals, model_names)
    )
    agg_result = await call_model(
        aggregator,
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
        temperature=0.1,
        timeout=AGGREGATOR_TIMEOUT_SECONDS,
    )

    elapsed = int((time.monotonic() - start) * 1000)
    agg_short = aggregator.name.split("/")[-1] if "/" in aggregator.name else aggregator.name

    if agg_result:
        _update_cost(cost, agg_result, is_aggregator=True)
        model_status[f"→{agg_short}"] = f"✅ {agg_result['latency_s']}s"
    else:
        model_status[f"→{agg_short}"] = "❌ failed"

    # Record spend
    record_spend(cost.estimated_cost_usd)

    return {
        "response": agg_result["content"] if agg_result else proposals[0],
        "proposals": proposals,
        "model_names": model_names,
        "model_status": model_status,
        "cost": cost,
        "latency_ms": elapsed,
        "warning": None if agg_result else "Aggregator failed — returning first proposal",
    }


# ══════════════════════════════════════════════════════════════════════════════
#  CASCADE — lite pass → confidence check → premium verification
# ══════════════════════════════════════════════════════════════════════════════

async def run_cascade(
    query: str,
    lite_tier: str = "lite",
    premium_tier: str = "ultra",
) -> Dict[str, Any]:
    """Run a cascade: lite MoA pass → confidence evaluation → premium if needed.

    Flow:
    1. Run lite MoA (cheap proposers → Sonnet)
    2. Haiku evaluates: are the models confident and in agreement?
    3. If confident → return lite result
    4. If not → run premium MoA (frontier proposers → Opus) with lite result as context
    """
    start = time.monotonic()

    # ── Step 1: Lite pass ──────────────────────────────────────────────────
    lite_result = await run_moa(query, tier_name=lite_tier)
    lite_cost = lite_result["cost"]

    # If only 1 proposer was available, skip confidence check — escalate
    if lite_cost.proposer_calls <= 1:
        premium_result = await run_moa(query, tier_name=premium_tier)
        premium_result["cost"].tier = f"cascade:{lite_tier}→{premium_tier}"
        premium_result["cost"].escalated = True
        premium_result["cost"].estimated_cost_usd += lite_cost.estimated_cost_usd
        premium_result["latency_ms"] = int((time.monotonic() - start) * 1000)
        return premium_result

    # ── Step 2: Confidence evaluation ──────────────────────────────────────
    evaluator = CLAUDE_HAIKU if CLAUDE_HAIKU.available else None
    if not evaluator:
        from .models import GEMINI_FLASH, GPT4O_MINI
        evaluator = GEMINI_FLASH if GEMINI_FLASH.available else GPT4O_MINI

    if not evaluator or not evaluator.available:
        return lite_result

    eval_context = (
        f"Original query: {query}\n\n"
        f"Synthesized answer:\n{lite_result['response']}\n\n"
        f"Individual model responses:\n"
    )
    for name, proposal in zip(
        lite_result.get("model_names", []), lite_result.get("proposals", [])
    ):
        eval_context += f"\n--- {name} ---\n{proposal[:1500]}\n"

    eval_result = await call_model(
        evaluator,
        [
            {"role": "system", "content": CASCADE_CONFIDENCE_PROMPT},
            {"role": "user", "content": eval_context},
        ],
        temperature=0.0,
        max_tokens=200,
    )

    confident = True
    escalation_reason = None

    if eval_result:
        _update_cost(lite_cost, eval_result)
        try:
            text = eval_result["content"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            judgment = json.loads(text)
            confident = judgment.get("confident", True)
            escalation_reason = judgment.get("reason", "")
        except (json.JSONDecodeError, KeyError):
            confident = True

    # ── Step 3: Return or escalate ─────────────────────────────────────────
    if confident:
        lite_result["cost"].tier = f"cascade:{lite_tier} (confident)"
        lite_result["latency_ms"] = int((time.monotonic() - start) * 1000)
        return lite_result

    # ── Step 4: Premium verification pass ──────────────────────────────────
    premium_query = (
        f"{query}\n\n"
        f"[Context: A previous analysis produced this answer, but a confidence "
        f"check flagged it as potentially unreliable because: {escalation_reason}. "
        f"Provide your own independent analysis.]\n\n"
        f"Previous answer for reference:\n{lite_result['response'][:2000]}"
    )

    premium_result = await run_moa(premium_query, tier_name=premium_tier)

    # Merge costs
    premium_cost = premium_result["cost"]
    premium_cost.proposer_calls += lite_cost.proposer_calls
    premium_cost.aggregator_calls += lite_cost.aggregator_calls
    premium_cost.total_input_tokens += lite_cost.total_input_tokens
    premium_cost.total_output_tokens += lite_cost.total_output_tokens
    premium_cost.models_used = lite_cost.models_used + premium_cost.models_used
    premium_cost.estimated_cost_usd += lite_cost.estimated_cost_usd
    premium_cost.tier = f"cascade:{lite_tier}→{premium_tier}"
    premium_cost.escalated = True

    premium_result["escalation_reason"] = escalation_reason
    premium_result["lite_response"] = lite_result["response"]
    premium_result["latency_ms"] = int((time.monotonic() - start) * 1000)

    return premium_result


# ══════════════════════════════════════════════════════════════════════════════
#  ADAPTIVE FLOW — classify → route → propose → detect agreement → synthesize
# ══════════════════════════════════════════════════════════════════════════════

async def classify_query(query: str) -> str:
    """Classify a query as SIMPLE, STANDARD, or COMPLEX using a cheap model.

    Returns the tier name string. Falls back to STANDARD on failure.
    """
    classifier = CLASSIFIER_MODEL if CLASSIFIER_MODEL.available else CLAUDE_HAIKU
    if not classifier or not classifier.available:
        return "STANDARD"

    result = await call_model(
        classifier,
        [
            {"role": "system", "content": CLASSIFY_QUERY_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0.0,
        max_tokens=50,
        timeout=10,
    )

    if not result:
        return "STANDARD"

    try:
        text = result["content"].strip()
        # Handle markdown-wrapped JSON
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        tier = parsed.get("tier", "STANDARD").upper()
        if tier in ("SIMPLE", "STANDARD", "COMPLEX"):
            return tier
    except (json.JSONDecodeError, KeyError, AttributeError):
        pass

    # Fallback: look for keywords
    text_upper = result["content"].upper()
    if "SIMPLE" in text_upper:
        return "SIMPLE"
    if "COMPLEX" in text_upper:
        return "COMPLEX"
    return "STANDARD"


def compute_agreement(proposals: list, model_names: list = None) -> dict:
    """Compute agreement between proposals using word overlap similarity.

    Returns dict with 'score' (0.0-1.0), 'consensus' (bool), and 'details'.
    Uses Jaccard similarity on significant words (>3 chars) across all pairs.
    """
    if len(proposals) < 2:
        return {"score": 1.0, "consensus": True, "details": "Only one proposal"}

    def significant_words(text: str) -> set:
        """Extract significant words (>3 chars, lowercase) from text."""
        return {
            w.lower().strip(".,!?;:()[]{}\"'")
            for w in text.split()
            if len(w) > 3
        }

    word_sets = [significant_words(p) for p in proposals]

    # Pairwise Jaccard similarity
    similarities = []
    for i in range(len(word_sets)):
        for j in range(i + 1, len(word_sets)):
            intersection = word_sets[i] & word_sets[j]
            union = word_sets[i] | word_sets[j]
            if union:
                similarities.append(len(intersection) / len(union))
            else:
                similarities.append(1.0)

    avg_sim = sum(similarities) / len(similarities) if similarities else 1.0
    consensus = avg_sim > 0.35  # Threshold: 35% word overlap = general agreement

    return {
        "score": round(avg_sim, 3),
        "consensus": consensus,
        "pairwise": similarities,
        "details": f"avg_similarity={avg_sim:.3f}, pairs={len(similarities)}",
    }


async def run_adaptive(query: str) -> Dict[str, Any]:
    """Adaptive routing: classify → route → propose → detect agreement → synthesize.

    Replaces the cascade with a smarter, more cost-efficient flow:
    1. Classify query as SIMPLE/STANDARD/COMPLEX (1 cheap call)
    2. Route to appropriate proposer pool
    3. Run proposers in parallel
    4. Detect agreement/disagreement
    5. If consensus: return best or synthesize
    6. If disagreement: run attribution synthesis (shows which model said what)
    """
    _check_budget_or_raise()

    start = time.monotonic()
    cost = QueryCost(tier="adaptive")
    model_status = {}

    # ── Step 1: Classify ───────────────────────────────────────────────────
    classification = await classify_query(query)
    tier = ADAPTIVE_TIERS.get(classification, ADAPTIVE_TIERS["STANDARD"])
    cost.tier = f"adaptive:{classification.lower()}"

    available = [m for m in tier.proposers if m.available]
    if not available:
        # Fallback to any available models
        from .models import available_models as get_available
        available = get_available()[:3]

    if not available:
        raise RuntimeError("No models available. Check API keys.")

    # ── Step 2: Parallel proposers ─────────────────────────────────────────
    user_msg = [{"role": "user", "content": query}]
    tasks = [call_model(m, user_msg) for m in available]
    results = await asyncio.gather(*tasks)

    proposals = []
    model_names = []

    for model, r in zip(available, results):
        short = model.name.split("/")[-1] if "/" in model.name else model.name
        if r:
            proposals.append(r["content"])
            model_names.append(short)
            _update_cost(cost, r)
            model_status[short] = f"✅ {r['latency_s']}s"
        else:
            model_status[short] = "❌ failed"

    if not proposals:
        raise RuntimeError("All proposers failed.")

    # ── SIMPLE tier: return best proposal directly ─────────────────────────
    if classification == "SIMPLE" or len(proposals) == 1:
        # Pick the longest (most complete) response
        best = max(proposals, key=len)
        elapsed = int((time.monotonic() - start) * 1000)
        record_spend(cost.estimated_cost_usd)
        return {
            "response": best,
            "proposals": proposals,
            "model_names": model_names,
            "model_status": model_status,
            "cost": cost,
            "latency_ms": elapsed,
            "classification": classification,
            "consensus": True,
            "agreement_score": 1.0,
        }

    # ── Step 3: Detect agreement ───────────────────────────────────────────
    agreement = compute_agreement(proposals, model_names)

    # ── Step 4: Synthesize based on agreement ─────────────────────────────
    synthesizer = tier.synthesizer
    if synthesizer and not synthesizer.available:
        from .models import get_aggregator
        synthesizer = get_aggregator(prefer_premium=(classification == "COMPLEX"))

    if agreement["consensus"]:
        # High agreement → clean synthesis (don't mention disagreement)
        if synthesizer:
            synth_prompt = CONSENSUS_AGGREGATOR_PROMPT.format(
                proposals=format_proposals(proposals, model_names)
            )
            synth_result = await call_model(
                synthesizer,
                [{"role": "system", "content": synth_prompt}, {"role": "user", "content": query}],
                temperature=0.1,
                timeout=AGGREGATOR_TIMEOUT_SECONDS,
            )
            if synth_result:
                _update_cost(cost, synth_result, is_aggregator=True)
                synth_short = synthesizer.name.split("/")[-1] if "/" in synthesizer.name else synthesizer.name
                model_status[f"→{synth_short}"] = f"✅ {synth_result['latency_s']}s"
                response = synth_result["content"]
            else:
                response = max(proposals, key=len)
        else:
            response = max(proposals, key=len)
    else:
        # Disagreement → attribution synthesis (show who said what)
        if synthesizer:
            synth_prompt = DISAGREEMENT_SYNTHESIS_PROMPT.format(
                query=query,
                proposals=format_proposals(proposals, model_names)
            )
            synth_result = await call_model(
                synthesizer,
                [{"role": "system", "content": synth_prompt}, {"role": "user", "content": query}],
                temperature=0.2,
                timeout=AGGREGATOR_TIMEOUT_SECONDS,
            )
            if synth_result:
                _update_cost(cost, synth_result, is_aggregator=True)
                synth_short = synthesizer.name.split("/")[-1] if "/" in synthesizer.name else synthesizer.name
                model_status[f"→{synth_short}"] = f"✅ {synth_result['latency_s']}s"
                response = synth_result["content"]
            else:
                # Fallback: show all proposals with headers
                parts = [f"## {name}\n{p}" for name, p in zip(model_names, proposals)]
                response = "⚠️ Models disagreed. Here are their individual positions:\n\n" + "\n\n---\n\n".join(parts)
        else:
            parts = [f"## {name}\n{p}" for name, p in zip(model_names, proposals)]
            response = "⚠️ Models disagreed. Here are their individual positions:\n\n" + "\n\n---\n\n".join(parts)

    elapsed = int((time.monotonic() - start) * 1000)
    record_spend(cost.estimated_cost_usd)

    return {
        "response": response,
        "proposals": proposals,
        "model_names": model_names,
        "model_status": model_status,
        "cost": cost,
        "latency_ms": elapsed,
        "classification": classification,
        "consensus": agreement["consensus"],
        "agreement_score": agreement["score"],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  EXPERT PANEL CODE REVIEW
# ══════════════════════════════════════════════════════════════════════════════

async def run_expert_review(
    diff: str,
    context: str = "",
) -> Dict[str, Any]:
    """Run Expert Panel code review with 4 specialized reviewers.

    Security + Architecture + Performance + Correctness → Synthesizer
    """
    from .config import MAX_DIFF_CHARS

    _check_budget_or_raise()

    cost = QueryCost(tier="expert-panel")
    start = time.monotonic()

    # Truncate oversized diffs
    diff_truncated = False
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS]
        diff_truncated = True

    review_prompt = f"Review this code change:\n\n{context}\n\n```diff\n{diff}\n```"

    available_roles = []
    for role in REVIEWER_ROLES:
        if role.model.available:
            available_roles.append((role, role.model))
        elif role.fallback.available:
            available_roles.append((role, role.fallback))

    if not available_roles:
        raise RuntimeError("No reviewer models available. Set at least one API key.")

    tasks = [
        call_model(
            model,
            [
                {"role": "system", "content": role.system_prompt},
                {"role": "user", "content": review_prompt},
            ],
        )
        for role, model in available_roles
    ]
    results = await asyncio.gather(*tasks)

    findings = []
    model_status = {}
    for (role, model), result in zip(available_roles, results):
        short = model.name.split("/")[-1] if "/" in model.name else model.name
        if result:
            findings.append({"role": role.name, "content": result["content"]})
            _update_cost(cost, result)
            model_status[role.name] = f"✅ {result['latency_s']}s ({short})"
        else:
            model_status[role.name] = f"❌ failed ({short})"

    if not findings:
        raise RuntimeError("All reviewers failed.")

    # ── Synthesize ─────────────────────────────────────────────────────────
    aggregator = get_aggregator(prefer_premium=True)
    if not aggregator:
        elapsed = int((time.monotonic() - start) * 1000)
        combined = "\n\n---\n\n".join(
            f"**{f['role']}:**\n{f['content']}" for f in findings
        )
        return {
            "response": combined, "findings": findings, "cost": cost,
            "model_status": model_status, "latency_ms": elapsed,
            "warning": "No aggregator — returning raw findings",
        }

    synth_system = CODE_REVIEW_AGGREGATOR.format(
        findings=format_review_findings(findings)
    )
    synth_result = await call_model(
        aggregator,
        [
            {"role": "system", "content": synth_system},
            {"role": "user", "content": f"Synthesize the review:\n\n```diff\n{diff[:3000]}\n```"},
        ],
        temperature=0.1,
        timeout=AGGREGATOR_TIMEOUT_SECONDS,
    )
    elapsed = int((time.monotonic() - start) * 1000)

    if synth_result:
        _update_cost(cost, synth_result, is_aggregator=True)
        agg_short = aggregator.name.split("/")[-1]
        model_status[f"→Synthesizer"] = f"✅ {synth_result['latency_s']}s ({agg_short})"

    result = {
        "response": synth_result["content"] if synth_result else findings[0]["content"],
        "findings": findings,
        "model_status": model_status,
        "cost": cost,
        "latency_ms": elapsed,
    }
    if diff_truncated:
        result["warning"] = f"Diff truncated to {MAX_DIFF_CHARS} chars. Full review may miss issues."
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  MULTI-ROUND DEBATE
# ══════════════════════════════════════════════════════════════════════════════

async def run_debate(
    query: str,
    rounds: int = 2,
    tier_name: str = "pro",
) -> Dict[str, Any]:
    """Run a multi-round debate where models revise based on each other.

    Round 0: Independent responses
    Rounds 1-N: Each model sees others' responses and revises
    Final: Judge synthesizes final positions
    """
    tier = TIERS.get(tier_name)
    if not tier:
        raise ValueError(f"Unknown tier: {tier_name}")

    available = tier.available_proposers
    if len(available) < 2:
        raise RuntimeError("Debate requires at least 2 available models.")

    cost = QueryCost(tier=f"debate-{tier_name}")
    start = time.monotonic()
    all_rounds = []
    model_status = {}

    # ── Round 0: Independent ───────────────────────────────────────────────
    tasks = [call_model(m, [{"role": "user", "content": query}]) for m in available]
    results = await asyncio.gather(*tasks)

    current_positions = {}
    for model, result in zip(available, results):
        short = model.name.split("/")[-1] if "/" in model.name else model.name
        if result:
            current_positions[model.name] = result["content"]
            _update_cost(cost, result)
            model_status[short] = f"✅ R0:{result['latency_s']}s"
        else:
            model_status[short] = "❌ failed R0"

    all_rounds.append(dict(current_positions))

    if len(current_positions) < 2:
        raise RuntimeError("Less than 2 models responded. Cannot debate.")

    # ── Debate rounds ──────────────────────────────────────────────────────
    for round_num in range(1, rounds + 1):
        revision_tasks = []
        revision_models = []

        for model in available:
            if model.name not in current_positions:
                continue
            others = {k: v for k, v in current_positions.items() if k != model.name}
            if not others:
                continue

            other_text = format_proposals(
                list(others.values()),
                [k.split("/")[-1] for k in others.keys()]
            )
            system = DEBATE_ROUND_SYSTEM.format(other_responses=other_text)

            revision_tasks.append(
                call_model(model, [
                    {"role": "system", "content": system},
                    {"role": "user", "content": query},
                ])
            )
            revision_models.append(model)

        results = await asyncio.gather(*revision_tasks)
        for model, result in zip(revision_models, results):
            short = model.name.split("/")[-1] if "/" in model.name else model.name
            if result:
                current_positions[model.name] = result["content"]
                _update_cost(cost, result)
                model_status[short] = f"✅ R{round_num}:{result['latency_s']}s"

        all_rounds.append(dict(current_positions))

    # ── Final judgment ─────────────────────────────────────────────────────
    aggregator = get_aggregator(prefer_premium=True)
    elapsed = int((time.monotonic() - start) * 1000)

    if not aggregator:
        return {
            "response": list(current_positions.values())[0],
            "rounds": all_rounds, "model_status": model_status,
            "cost": cost, "latency_ms": elapsed,
        }

    final_text = format_proposals(
        list(current_positions.values()),
        [k.split("/")[-1] for k in current_positions.keys()]
    )
    judge_result = await call_model(
        aggregator,
        [
            {"role": "system", "content": DEBATE_JUDGE_SYSTEM.format(final_positions=final_text)},
            {"role": "user", "content": query},
        ],
        temperature=0.1,
        timeout=AGGREGATOR_TIMEOUT_SECONDS,
    )

    elapsed = int((time.monotonic() - start) * 1000)
    if judge_result:
        _update_cost(cost, judge_result, is_aggregator=True)

    return {
        "response": judge_result["content"] if judge_result else list(current_positions.values())[0],
        "rounds": all_rounds,
        "model_status": model_status,
        "cost": cost,
        "latency_ms": elapsed,
    }

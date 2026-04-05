"""Adaptive routing, MoA, cascade, deep research, and session memory."""

import asyncio
import json
import time
from typing import List, Optional, Dict, Any

from .config import (
    AGGREGATOR_TIMEOUT_SECONDS,
)
from .budget import record_spend
from .models import (
    ModelConfig, Tier, QueryCost,
    TIERS, get_aggregator,
    CLAUDE_HAIKU, CASCADE_CONFIDENCE_PROMPT,
    AdaptiveTier, ADAPTIVE_TIERS, CLASSIFIER_MODEL,
)
from .prompts import (
    MOA_AGGREGATOR_SYSTEM, MOA_VERIFY_SYSTEM, STRATEGIC_ADDENDUM,
    format_proposals,
    CLASSIFY_QUERY_PROMPT, DISAGREEMENT_SYNTHESIS_PROMPT, CONSENSUS_AGGREGATOR_PROMPT,
    FACTUAL_VERIFICATION_PROMPT,
)
from .orchestrator import (
    call_model, _check_budget_or_raise, _update_cost,
    compute_agreement, pairwise_rank,
)


# ══════════════════════════════════════════════════════════════════════════════
#  MIXTURE OF AGENTS — standard 2-layer pattern
# ══════════════════════════════════════════════════════════════════════════════

async def run_moa(
    query: str,
    tier_name: str = "lite",
    layers: int = 1,
) -> Dict[str, Any]:
    """Run a multi-layer Mixture-of-Agents query.

    Layer 1: Parallel proposers generate independent responses.
    Aggregation: Aggregator synthesizes proposals into one high-quality response.
    Layer 2+ (optional): Proposers verify synthesis, re-aggregate.
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

    response = agg_result["content"] if agg_result else proposals[0]

    # ── Additional layers: proposers verify synthesis ─────────────────────
    for layer_num in range(2, layers + 1):
        verify_prompt = MOA_VERIFY_SYSTEM.format(
            synthesis=response,
            proposals=format_proposals(proposals, model_names),
        )
        verify_tasks = [
            call_model(m, [
                {"role": "system", "content": verify_prompt},
                {"role": "user", "content": query},
            ])
            for m in available
        ]
        verify_results = await asyncio.gather(*verify_tasks)

        verify_proposals = []
        verify_names = []
        for model, r in zip(available, verify_results):
            short = model.name.split("/")[-1] if "/" in model.name else model.name
            if r:
                verify_proposals.append(r["content"])
                verify_names.append(short)
                _update_cost(cost, r)
                model_status[f"{short}:L{layer_num}"] = f"✅ {r['latency_s']}s"

        if verify_proposals:
            # Re-aggregate verified proposals
            verify_agg_prompt = MOA_AGGREGATOR_SYSTEM.format(
                proposals=format_proposals(verify_proposals, verify_names)
            )
            re_agg = await call_model(
                aggregator,
                [{"role": "system", "content": verify_agg_prompt}, {"role": "user", "content": query}],
                temperature=0.1,
                timeout=AGGREGATOR_TIMEOUT_SECONDS,
            )
            if re_agg:
                response = re_agg["content"]
                _update_cost(cost, re_agg, is_aggregator=True)

    elapsed = int((time.monotonic() - start) * 1000)

    # Record spend
    record_spend(cost.estimated_cost_usd)

    return {
        "response": response,
        "proposals": proposals,
        "model_names": model_names,
        "model_status": model_status,
        "cost": cost,
        "latency_ms": elapsed,
        "layers": layers,
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
    """Run a cascade: lite MoA pass -> confidence evaluation -> premium if needed."""
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

# Domain-specific agreement thresholds (from duh)
DOMAIN_CONFIDENCE_CAPS = {
    "FACTUAL": 0.45,     # High bar — models should agree on facts
    "TECHNICAL": 0.40,   # Moderate — some implementation opinions OK
    "CREATIVE": 0.30,    # Low bar — diversity is expected
    "JUDGMENT": 0.25,    # Very low — genuine opinion splits normal
    "STRATEGIC": 0.20,   # Lowest — complex decisions always diverge
}
DEFAULT_AGREEMENT_THRESHOLD = 0.35


async def classify_query(query: str) -> Dict[str, str]:
    """Classify a query's complexity tier and domain using a cheap model.

    Returns dict with 'tier' and 'domain'. Falls back to STANDARD/TECHNICAL.
    """
    classifier = CLASSIFIER_MODEL if CLASSIFIER_MODEL.available else CLAUDE_HAIKU
    if not classifier or not classifier.available:
        return {"tier": "STANDARD", "domain": "TECHNICAL"}

    result = await call_model(
        classifier,
        [
            {"role": "system", "content": CLASSIFY_QUERY_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0.0,
        max_tokens=100,
        timeout=10,
    )

    if not result:
        return {"tier": "STANDARD", "domain": "TECHNICAL"}

    try:
        text = result["content"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        tier = parsed.get("tier", "STANDARD").upper()
        domain = parsed.get("domain", "TECHNICAL").upper()
        if tier not in ("SIMPLE", "STANDARD", "COMPLEX"):
            tier = "STANDARD"
        if domain not in DOMAIN_CONFIDENCE_CAPS:
            domain = "TECHNICAL"
        return {"tier": tier, "domain": domain}
    except (json.JSONDecodeError, KeyError, AttributeError):
        pass

    # Fallback: look for keywords
    text_upper = result["content"].upper()
    tier = "STANDARD"
    if "SIMPLE" in text_upper:
        tier = "SIMPLE"
    elif "COMPLEX" in text_upper:
        tier = "COMPLEX"
    return {"tier": tier, "domain": "TECHNICAL"}


async def _verify_factual_claims(
    query: str, proposals: List[str], model_names: List[str]
) -> Optional[Dict[str, Any]]:
    """Use a cheap model to check proposals for suspicious precision or inconsistency."""
    model = CLASSIFIER_MODEL if CLASSIFIER_MODEL.available else CLAUDE_HAIKU
    if not model or not model.available:
        return None

    proposals_text = format_proposals(proposals[:3], model_names[:3])
    result = await call_model(
        model,
        [
            {"role": "system", "content": FACTUAL_VERIFICATION_PROMPT},
            {"role": "user", "content": f"Question: {query}\n\nResponses:\n{proposals_text}"},
        ],
        temperature=0.0,
        max_tokens=200,
        timeout=10,
    )

    if not result:
        return None

    try:
        text = result["content"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        return {
            "suspicious": parsed.get("suspicious", False),
            "warning": parsed.get("warning", ""),
            "claims_checked": parsed.get("claims", []),
        }
    except (json.JSONDecodeError, KeyError, AttributeError):
        return None


async def run_adaptive(query: str, research_mode: str = "auto") -> Dict[str, Any]:
    """Adaptive routing: classify -> route -> propose -> detect agreement -> synthesize."""
    _check_budget_or_raise()

    start = time.monotonic()
    cost = QueryCost(tier="adaptive")
    model_status = {}

    # ── Step 1: Classify ───────────────────────────────────────────────────
    query_class = await classify_query(query)
    classification = query_class["tier"]
    domain = query_class["domain"]
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
            "domain": domain,
            "consensus": True,
            "agreement_score": 1.0,
        }

    # ── Step 3: Detect agreement (domain-capped threshold) ────────────────
    agreement = compute_agreement(proposals, model_names)
    threshold = DOMAIN_CONFIDENCE_CAPS.get(domain, DEFAULT_AGREEMENT_THRESHOLD)
    agreement["consensus"] = agreement["score"] > threshold

    # ── Step 3b: Correlated confidence warning ─────────────────────────────
    confidence_warning = None
    if (
        agreement["consensus"]
        and agreement["score"] > 0.6
        and classification in ("STANDARD", "COMPLEX")
        and domain in ("TECHNICAL", "FACTUAL")
    ):
        confidence_warning = (
            "High agreement on a specific topic. Models may share the same "
            "training data gap. Consider verifying key claims independently."
        )

    # ── Step 3c: Factual verification (for FACTUAL domain with high agreement) ─
    verification_result = None
    if (
        agreement["consensus"]
        and domain == "FACTUAL"
        and classification != "SIMPLE"
    ):
        verification_result = await _verify_factual_claims(query, proposals, model_names)
        if verification_result and verification_result.get("suspicious"):
            confidence_warning = verification_result["warning"]

    # ── Step 3d: Pairwise ranking (for STANDARD/COMPLEX) ─────────────────
    ranking = await pairwise_rank(proposals, model_names)

    # ── Step 3e: Session context for consistency ────────────────────────────
    session_ctx = get_session_context()
    session_note = ""
    if session_ctx:
        session_note = (
            "\n\n[SESSION CONTEXT — previous answers this session]\n"
            f"{session_ctx}\n"
            "[/SESSION CONTEXT]\n"
            "If your answer contradicts a previous answer in this session, "
            "explicitly acknowledge the contradiction and explain why."
        )

    # ── Step 4: Synthesize based on agreement ─────────────────────────────
    synthesizer = tier.synthesizer
    if synthesizer and not synthesizer.available:
        from .models import get_aggregator
        synthesizer = get_aggregator(prefer_premium=(classification == "COMPLEX"))

    # Add strategic analysis sections for STRATEGIC/JUDGMENT queries
    strategic_extra = STRATEGIC_ADDENDUM if domain in ("STRATEGIC", "JUDGMENT") else ""

    if agreement["consensus"]:
        # High agreement -> clean synthesis (don't mention disagreement)
        if synthesizer:
            synth_prompt = CONSENSUS_AGGREGATOR_PROMPT.format(
                proposals=format_proposals(proposals, model_names)
            ) + strategic_extra
            synth_result = await call_model(
                synthesizer,
                [{"role": "system", "content": synth_prompt + session_note}, {"role": "user", "content": query}],
                temperature=0.1,
                timeout=AGGREGATOR_TIMEOUT_SECONDS,
            )
            if synth_result:
                _update_cost(cost, synth_result, is_aggregator=True)
                synth_short = synthesizer.name.split("/")[-1] if "/" in synthesizer.name else synthesizer.name
                model_status[f"→{synth_short}"] = f"✅ {synth_result['latency_s']}s"
                response = synth_result["content"]
            else:
                response = proposals[ranking["best_index"]]
        else:
            response = proposals[ranking["best_index"]]
    else:
        # Disagreement -> try research-augmented re-ask, then attribution synthesis
        research_context = None
        if research_mode != "off":
            from .research import lite_search, get_search_provider
            provider = get_search_provider()
            if provider:
                research_context = await lite_search(query, provider)

        if research_context:
            # Re-run same proposers with research context
            augmented_query = (
                f"[REFERENCE CONTEXT]\n{research_context}\n[/REFERENCE CONTEXT]\n\n{query}"
            )
            augmented_msg = [{"role": "user", "content": augmented_query}]
            re_tasks = [call_model(m, augmented_msg) for m in available]
            re_results = await asyncio.gather(*re_tasks)

            re_proposals = []
            re_model_names = []
            for model, r in zip(available, re_results):
                short = model.name.split("/")[-1] if "/" in model.name else model.name
                if r:
                    re_proposals.append(r["content"])
                    re_model_names.append(short)
                    _update_cost(cost, r)
                    model_status[f"{short}:re"] = f"✅ {r['latency_s']}s"

            if re_proposals:
                proposals = re_proposals
                model_names = re_model_names
                cost.tier += "+research"

        # Synthesize (works whether we re-asked or not)
        if synthesizer:
            synth_prompt = DISAGREEMENT_SYNTHESIS_PROMPT.format(
                query=query,
                proposals=format_proposals(proposals, model_names)
            ) + strategic_extra
            synth_result = await call_model(
                synthesizer,
                [{"role": "system", "content": synth_prompt + session_note}, {"role": "user", "content": query}],
                temperature=0.2,
                timeout=AGGREGATOR_TIMEOUT_SECONDS,
            )
            if synth_result:
                _update_cost(cost, synth_result, is_aggregator=True)
                synth_short = synthesizer.name.split("/")[-1] if "/" in synthesizer.name else synthesizer.name
                model_status[f"→{synth_short}"] = f"✅ {synth_result['latency_s']}s"
                response = synth_result["content"]
            else:
                parts = [f"## {name}\n{p}" for name, p in zip(model_names, proposals)]
                response = "⚠️ Models disagreed. Here are their individual positions:\n\n" + "\n\n---\n\n".join(parts)
        else:
            parts = [f"## {name}\n{p}" for name, p in zip(model_names, proposals)]
            response = "⚠️ Models disagreed. Here are their individual positions:\n\n" + "\n\n---\n\n".join(parts)

    elapsed = int((time.monotonic() - start) * 1000)
    record_spend(cost.estimated_cost_usd)

    # ── Session memory: log key claims for cross-query consistency ───────
    _log_session_claims(query, response)

    result_dict = {
        "response": response,
        "proposals": proposals,
        "model_names": model_names,
        "model_status": model_status,
        "cost": cost,
        "latency_ms": elapsed,
        "classification": classification,
        "domain": domain,
        "consensus": agreement["consensus"],
        "agreement_score": agreement["score"],
        "agreement_threshold": threshold,
        "ranking": ranking,
        "researched": research_context is not None,
    }
    if confidence_warning:
        result_dict["confidence_warning"] = confidence_warning
    if verification_result:
        result_dict["verification"] = verification_result

    return result_dict


# ── Session memory for cross-query consistency ────────────────────────────────

_SESSION_FILE = None


def _get_session_file():
    """Get or create the session file path for today."""
    global _SESSION_FILE
    if _SESSION_FILE is None:
        from .config import MOA_HOME
        import datetime
        today = datetime.date.today().isoformat()
        session_dir = MOA_HOME / "sessions"
        session_dir.mkdir(exist_ok=True)
        _SESSION_FILE = session_dir / f"session-{today}.jsonl"
    return _SESSION_FILE


def _log_session_claims(query: str, response: str):
    """Log query + response summary to session file for consistency checking."""
    import datetime
    session_file = _get_session_file()
    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "query": query[:200],
        "response_preview": response[:500],
    }
    try:
        with open(session_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Non-critical — don't crash on write failure


def get_session_context() -> str:
    """Read today's session history for consistency checking."""
    session_file = _get_session_file()
    if not session_file.exists():
        return ""
    try:
        lines = session_file.read_text().strip().split("\n")
        recent = lines[-5:]  # Last 5 queries
        parts = []
        for line in recent:
            entry = json.loads(line)
            parts.append(f"Q: {entry['query']}\nA: {entry['response_preview']}")
        return "\n\n---\n\n".join(parts)
    except (OSError, json.JSONDecodeError):
        return ""


# ══════════════════════════════════════════════════════════════════════════════
#  DEEP RESEARCH
# ══════════════════════════════════════════════════════════════════════════════

async def run_deep_research(query: str) -> Dict[str, Any]:
    """Deep research mode: multi-hop search -> single frontier model synthesis."""
    from .research import deep_research, get_search_provider
    from .prompts import DEEP_RESEARCH_SYNTHESIS_PROMPT
    from .models import get_aggregator

    _check_budget_or_raise()
    start = time.monotonic()
    cost = QueryCost(tier="deep-research")

    provider = get_search_provider()
    if not provider:
        raise RuntimeError(
            "Deep research requires FIRECRAWL_API_KEY. "
            "Set it in .env or environment."
        )

    progress_updates = []

    def on_progress(msg):
        progress_updates.append(msg)

    context = await deep_research(query, provider, on_progress=on_progress)
    if not context:
        raise RuntimeError("Research produced no results. Try rephrasing the query.")

    # Single frontier model with full context
    model = get_aggregator(prefer_premium=True)
    messages = [
        {"role": "system", "content": DEEP_RESEARCH_SYNTHESIS_PROMPT},
        {
            "role": "user",
            "content": f"[RESEARCH CONTEXT]\n{context}\n[/RESEARCH CONTEXT]\n\nQuestion: {query}",
        },
    ]

    result = await call_model(
        model, messages, temperature=0.2, timeout=AGGREGATOR_TIMEOUT_SECONDS
    )
    if not result:
        raise RuntimeError("Synthesis model failed after research.")

    _update_cost(cost, result, is_aggregator=True)
    elapsed = int((time.monotonic() - start) * 1000)
    record_spend(cost.estimated_cost_usd)

    model_short = model.name.split("/")[-1] if "/" in model.name else model.name

    return {
        "response": result["content"],
        "model_status": {model_short: f"✅ {result['latency_s']}s"},
        "cost": cost,
        "latency_ms": elapsed,
        "research_steps": progress_updates,
    }

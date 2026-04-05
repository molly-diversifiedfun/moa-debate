"""Multi-round debate: peer and adversarial (angel/devil/judge) patterns."""

import asyncio
import re
import time
import unicodedata
from typing import List, Optional, Dict, Any, Callable

from .config import DEBATE_TIMEOUT_SECONDS, AGGREGATOR_TIMEOUT_SECONDS
from .budget import record_spend
from .models import (
    QueryCost, TIERS, get_aggregator,
)
from .prompts import (
    DEBATE_ROUND_SYSTEM, DEBATE_JUDGE_SYSTEM, STRATEGIC_ADDENDUM,
    format_proposals,
    DEBATE_CHALLENGE_SYSTEM, DEBATE_REVISION_WITH_CHALLENGES_SYSTEM,
    DEBATE_ANGEL_SYSTEM, DEBATE_DEVIL_SYSTEM, DEBATE_ADVERSARIAL_JUDGE_SYSTEM,
)
from .orchestrator import call_model, _check_budget_or_raise, _update_cost, compute_agreement


async def run_debate(
    query: str,
    rounds: int = 2,
    tier_name: str = "pro",
    debate_style: str = "peer",
    on_progress: Optional[Callable] = None,
    template_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a multi-round debate where models revise based on each other.

    Peer style (default):
      Round 0: Independent responses
      Challenge: Models find flaws in others' responses
      Rounds 1-N: Models revise, addressing challenges. Early exit if convergence >0.7.
      Final: Judge synthesizes

    Adversarial style (--style adversarial):
      Round 0: Angel argues FOR, Devil argues AGAINST
      Rounds 1-N: Each sees the other's position and revises
      Final: Judge synthesizes both perspectives
    """
    _progress = on_progress or (lambda msg: None)

    if debate_style == "adversarial":
        return await _run_adversarial_debate(query, rounds, tier_name, on_progress=_progress, template_name=template_name)

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
    converged_at = None

    # ── Round 0: Independent ───────────────────────────────────────────────
    names = [m.name.split("/")[-1] if "/" in m.name else m.name for m in available]
    _progress(f"📝 {len(available)} models forming independent opinions... ({', '.join(names)})")
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

    # ── Challenge round: find flaws before revision ────────────────────────
    _progress("🔍 Challenge round: \"Find something wrong. No, really. We insist.\"")
    challenges_by_model = {}
    challenge_tasks = []
    challenge_models = []

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
        challenge_tasks.append(
            call_model(model, [
                {"role": "system", "content": DEBATE_CHALLENGE_SYSTEM.format(other_responses=other_text)},
                {"role": "user", "content": query},
            ])
        )
        challenge_models.append(model)

    challenge_results = await asyncio.gather(*challenge_tasks)
    for model, result in zip(challenge_models, challenge_results):
        short = model.name.split("/")[-1] if "/" in model.name else model.name
        if result:
            challenges_by_model[model.name] = result["content"]
            _update_cost(cost, result)
            model_status[short] = f"✅ CH:{result['latency_s']}s"

    # ── Debate rounds with convergence check ───────────────────────────────
    round_messages = [
        "⚔️  Round {n}: Models read the challenges. Egos bruised. Revising...",
        "🔄 Round {n}: \"Actually, you make a fair point...\" (or not)",
        "🤔 Round {n}: Models reconsider. Some dig in. Some fold.",
    ]
    for round_num in range(1, rounds + 1):
        msg = round_messages[(round_num - 1) % len(round_messages)].format(n=round_num)
        _progress(msg)
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

            # First revision round: include challenges
            if round_num == 1 and challenges_by_model:
                # Gather challenges OF this model (from others)
                relevant_challenges = {
                    k: v for k, v in challenges_by_model.items() if k != model.name
                }
                if relevant_challenges:
                    challenge_text = format_proposals(
                        list(relevant_challenges.values()),
                        [k.split("/")[-1] for k in relevant_challenges.keys()]
                    )
                    system = DEBATE_REVISION_WITH_CHALLENGES_SYSTEM.format(
                        challenges=challenge_text,
                        other_responses=other_text,
                    )
                else:
                    system = DEBATE_ROUND_SYSTEM.format(other_responses=other_text)
            else:
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

        # Convergence check: early exit if models agree
        agreement = compute_agreement(list(current_positions.values()))
        if agreement["score"] > 0.7:
            converged_at = round_num
            _progress(f"🤝 Consensus reached at round {round_num}! Agreement: {agreement['score']:.0%}. They actually agree now.")
            break
        else:
            _progress(f"   📊 Agreement: {agreement['score']:.0%} — still fighting.")

    # ── Final judgment ─────────────────────────────────────────────────────
    _progress("⚖️  Judge enters the room. Reviewing all arguments...")
    aggregator = get_aggregator(prefer_premium=True)
    elapsed = int((time.monotonic() - start) * 1000)

    if not aggregator:
        return {
            "response": list(current_positions.values())[0],
            "rounds": all_rounds, "model_status": model_status,
            "cost": cost, "latency_ms": elapsed,
            "converged_at": converged_at,
        }

    final_text = format_proposals(
        list(current_positions.values()),
        [k.split("/")[-1] for k in current_positions.keys()]
    )
    judge_result = await call_model(
        aggregator,
        [
            {"role": "system", "content": DEBATE_JUDGE_SYSTEM.format(final_positions=final_text) + STRATEGIC_ADDENDUM},
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
        "converged_at": converged_at,
    }


# ── Display width helpers for battle card ──────────────────────────────────────

def _dw(s: str) -> int:
    """Terminal display width — handles emoji vs ASCII correctly."""
    w = 0
    for i, c in enumerate(s):
        cp = ord(c)
        if cp == 0xFE0F:
            # VS16 forces emoji presentation — preceding char renders as width 2.
            # We already counted it as 1, so add 1 to upgrade.
            w += 1
            continue
        eaw = unicodedata.east_asian_width(c)
        if eaw in ("W", "F") or cp > 0x1F000:
            w += 2
        else:
            w += 1
    return w


# ── Best sentence extraction for debate previews ──────────────────────────────

_SKIP_PREFIXES = (
    "i need to", "let me", "as the advocate", "as the critic",
    "as your advocate", "i'll build", "i want to", "to answer this",
    "this is a", "here's my", "my argument", "i'm going to",
    "opening argument", "the evidence strongly", "the strongest argument",
)
# Signals of a meaty, specific sentence worth showing
_SPECIFICITY_SIGNALS = [
    "%", "$", "study", "research", "data", "evidence", "found that",
    "showed", "according", "published", "trial", "patients", "users",
    "companies", "however", "concede", "but", "critical", "risk",
    "failure", "success", "rate", "year", "month", "week",
]


def _best_sentence(text: str) -> str:
    """Find the most specific, interesting sentence — not the opening."""
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text.replace("\n", " ").strip())
    # Score each sentence by specificity
    scored = []
    for s in sentences:
        stripped = s.strip().lstrip("#*-– ")
        if len(stripped) < 20 or len(stripped) > 250:
            continue
        lower = stripped.lower()
        if lower.startswith(_SKIP_PREFIXES):
            continue
        # Score: more specificity signals = more interesting
        score = sum(1 for sig in _SPECIFICITY_SIGNALS if sig in lower)
        # Bonus for numbers (specific data)
        score += len(re.findall(r'\d+', stripped))
        scored.append((score, stripped))
    if not scored:
        # Fallback to first non-preamble sentence
        for s in sentences:
            stripped = s.strip().lstrip("#*-– ")
            if len(stripped) >= 20 and not stripped.lower().startswith(_SKIP_PREFIXES):
                return stripped[:200]
        return text.replace("\n", " ").strip()[:150]
    # Return the highest-scored sentence
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1][:200]


def _word_count(text: str) -> int:
    return len(text.split())


# ══════════════════════════════════════════════════════════════════════════════
#  ADVERSARIAL DEBATE — Angel/Devil/Judge
# ══════════════════════════════════════════════════════════════════════════════

async def _run_adversarial_debate(
    query: str,
    rounds: int = 2,
    tier_name: str = "pro",
    on_progress: Optional[Callable] = None,
    template_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Angel/Devil/Judge debate: one model argues FOR, one AGAINST, judge synthesizes."""
    _progress = on_progress or (lambda msg: None)

    # ── Template resolution ───────────────────────────────────────────────
    from .templates import get_template, detect_template, DecisionTemplate
    template: Optional[DecisionTemplate] = None
    if template_name:
        template = get_template(template_name)
        if template:
            _progress(f"📋 Using '{template.name}' template: {template.description}")
        else:
            _progress(f"⚠️  Unknown template '{template_name}' — running without template")
    else:
        template = detect_template(query)
        if template:
            _progress(f"💡 Auto-detected '{template.name}' template — using domain framing")
    tier = TIERS.get(tier_name)
    if not tier:
        raise ValueError(f"Unknown tier: {tier_name}")

    # For adversarial debate, use the STRONGEST HEALTHY models across ALL tiers.
    # Skip models with open circuit breakers — they'll just waste time.
    from .models import available_models as get_all_available
    from .health import should_skip
    all_available = get_all_available()
    # Filter out circuit-broken models, then rank by capability
    healthy = [m for m in all_available if not should_skip(m.name)]
    if len(healthy) < 2:
        # Fall back to all available if not enough healthy ones
        healthy = all_available
    if len(healthy) < 2:
        raise RuntimeError("Adversarial debate requires at least 2 available models.")

    # Sort by capability (output cost as proxy) — most expensive = strongest
    ranked = sorted(healthy, key=lambda m: m.output_cost_per_mtok, reverse=True)
    angel_model = ranked[0]
    # Devil must be from a DIFFERENT provider for genuine diversity
    devil_model = next(
        (m for m in ranked[1:] if m.provider != angel_model.provider),
        ranked[1],
    )
    # Log if we downgraded from the top models
    all_ranked = sorted(all_available, key=lambda m: m.output_cost_per_mtok, reverse=True)
    if all_ranked[0].name != angel_model.name or (len(all_ranked) > 1 and all_ranked[1].name != devil_model.name):
        skipped_names = [m.name.split("/")[-1] for m in all_ranked if should_skip(m.name)]
        if skipped_names:
            _progress(f"⚡ Skipping unhealthy models: {', '.join(skipped_names)}")
    cost = QueryCost(tier=f"adversarial-{tier_name}")
    start = time.monotonic()
    all_rounds = []
    model_status = {}
    converged_at = None

    angel_short = angel_model.name.split("/")[-1] if "/" in angel_model.name else angel_model.name
    devil_short = devil_model.name.split("/")[-1] if "/" in devil_model.name else devil_model.name

    # ── Round 0: Independent positions ─────────────────────────────────────
    _label_advocate = f"Advocate: {angel_short}"
    _label_critic   = f"Critic:   {devil_short}"
    # inner width in display columns (content area between borders)
    _adv_content = f"  👼 {_label_advocate}"
    _crt_content = f"  😈 {_label_critic}"
    _title_text  = "⚔️  ADVERSARIAL DEBATE  ⚔️"
    _quote       = '"Let them fight."'
    _quote_content = f"  {_quote}"
    _inner = max(_dw(_adv_content), _dw(_crt_content), _dw(_title_text), _dw(_quote_content)) + 4
    _top    = "╔" + "═" * _inner + "╗"
    _bottom = "╚" + "═" * _inner + "╝"
    _blank  = "║" + " " * _inner + "║"
    # Pad each line: (inner - display_width) spaces after content
    def _pad_line(content: str) -> str:
        return "║" + content + " " * (_inner - _dw(content)) + "║"
    def _center_line(content: str) -> str:
        pad = _inner - _dw(content)
        left = pad // 2
        right = pad - left
        return "║" + " " * left + content + " " * right + "║"
    _progress(
        f"{_top}\n"
        f"{_center_line(_title_text)}\n"
        f"{_blank}\n"
        f"{_pad_line(_adv_content)}\n"
        f"{_pad_line(_crt_content)}\n"
        f"{_blank}\n"
        f"{_center_line(_quote_content)}\n"
        f"{_bottom}"
    )
    # ── Research phase: ground the debate in real sources ────────────────
    # Use all available providers (Firecrawl + DuckDuckGo) with fallback chain
    research_context = ""
    try:
        from .research import get_all_providers, format_research_context
        providers = get_all_providers()
        if providers:
            provider_names = [type(p).__name__.replace("Provider", "") for p in providers]
            _progress(f"🔍 Researching both sides ({' → '.join(provider_names)})...")
            all_results: list = []
            seen_urls: set = set()
            # Search pro/con angles across all providers
            search_queries = [
                query,
                f"arguments for {query}",
                f"arguments against {query}",
                f"{query} evidence research data",
            ]
            # Add template-specific research queries
            if template:
                search_queries.extend(template.research_queries)
            for provider in providers:
                for sq in search_queries:
                    try:
                        results = await provider.search(sq, max_results=3)
                        for r in results:
                            if r.url and r.url not in seen_urls:
                                seen_urls.add(r.url)
                                all_results.append(r)
                    except Exception:
                        continue
                # If first provider got enough, skip supplementing
                if len(all_results) >= 6:
                    break
            if all_results:
                from .config import RESEARCH_CONTEXT_MAX_CHARS_DEEP
                research_context = format_research_context(all_results, max_chars=RESEARCH_CONTEXT_MAX_CHARS_DEEP)
            if research_context:
                source_count = research_context.count("Source: http")
                _progress(f"📚 Found {source_count} sources — both sides will cite real evidence")
            else:
                _progress("📚 No research results — debating from training data")
    except Exception:
        pass  # research is best-effort, debate continues without it

    # Inject template context + research into prompts
    angel_system = DEBATE_ANGEL_SYSTEM.format(previous_round="This is your opening argument.")
    devil_system = DEBATE_DEVIL_SYSTEM.format(previous_round="This is your opening argument.")
    # Template: light context for debaters (what kind of decision, not what to argue)
    if template:
        angel_system += f"\n\nDecision context: {template.debater_context}"
        devil_system += f"\n\nDecision context: {template.debater_context}"
    if research_context:
        cite_instruction = "\n\nCite specific sources from the research when making claims. Reference data, studies, or examples by name."
        angel_system += f"\n\n{research_context}{cite_instruction}"
        devil_system += f"\n\n{research_context}{cite_instruction}"

    _progress("__FIGHT_START__")
    angel_task = call_model(angel_model, [
        {"role": "system", "content": angel_system},
        {"role": "user", "content": query},
    ], timeout=DEBATE_TIMEOUT_SECONDS)
    devil_task = call_model(devil_model, [
        {"role": "system", "content": devil_system},
        {"role": "user", "content": query},
    ], timeout=DEBATE_TIMEOUT_SECONDS)

    angel_r, devil_r = await asyncio.gather(angel_task, devil_task)
    _progress("__FIGHT_STOP__")

    angel_pos = angel_r["content"] if angel_r else ""
    devil_pos = devil_r["content"] if devil_r else ""

    if angel_r:
        _update_cost(cost, angel_r)
        model_status[f"👼 {angel_short}"] = f"✅ R0:{angel_r['latency_s']}s"
    else:
        model_status[f"👼 {angel_short}"] = "❌ failed R0"
    if devil_r:
        _update_cost(cost, devil_r)
        model_status[f"😈 {devil_short}"] = f"✅ R0:{devil_r['latency_s']}s"
    else:
        model_status[f"😈 {devil_short}"] = "❌ failed R0"

    # If one side failed, try fallback models
    if not angel_pos or not devil_pos:
        remaining = [m for m in ranked[2:] if m.available] if len(ranked) > 2 else []
        if not angel_pos and remaining:
            angel_model = remaining[0]
            angel_short = angel_model.name.split("/")[-1] if "/" in angel_model.name else angel_model.name
            fb = await call_model(angel_model, [
                {"role": "system", "content": DEBATE_ANGEL_SYSTEM.format(previous_round="This is your opening argument.")},
                {"role": "user", "content": query},
            ])
            if fb:
                angel_pos = fb["content"]
                _update_cost(cost, fb)
                model_status[f"👼 {angel_short}"] = f"✅ R0:{fb['latency_s']}s (fallback)"
        if not devil_pos and remaining:
            fb_model = remaining[-1] if len(remaining) > 1 else remaining[0]
            devil_short_fb = fb_model.name.split("/")[-1] if "/" in fb_model.name else fb_model.name
            if fb_model.name != angel_model.name if not angel_pos else True:
                fb = await call_model(fb_model, [
                    {"role": "system", "content": DEBATE_DEVIL_SYSTEM.format(previous_round="This is your opening argument.")},
                    {"role": "user", "content": query},
                ])
                if fb:
                    devil_pos = fb["content"]
                    devil_model = fb_model
                    devil_short = devil_short_fb
                    _update_cost(cost, fb)
                    model_status[f"😈 {devil_short}"] = f"✅ R0:{fb['latency_s']}s (fallback)"

    if not angel_pos or not devil_pos:
        raise RuntimeError(
            "Adversarial debate requires 2 responding models. "
            "Available models may be rate-limited or unavailable."
        )

    all_rounds.append({"angel": angel_pos, "devil": devil_pos})

    angel_thesis = _best_sentence(angel_pos)
    devil_thesis = _best_sentence(devil_pos)
    _progress(f"\n   👼 ADVOCATE opens:")
    _progress(f"   │ \"{angel_thesis}\"")
    _progress(f"   │ ({_word_count(angel_pos)} words)")
    _progress(f"\n   😈 CRITIC opens:")
    _progress(f"   │ \"{devil_thesis}\"")
    _progress(f"   │ ({_word_count(devil_pos)} words)")

    # ── Debate rounds with auto-extension ──────────────────────────────────
    prev_agreement_score = compute_agreement([angel_pos, devil_pos])["score"]
    _progress(f"\n   📊 Opening agreement: {prev_agreement_score:.0%}")

    adversarial_round_msgs = [
        "⚔️  Round {n}: They've read each other's arguments. Gloves are off.",
        "🔥 Round {n}: \"That's your best argument?\" Both sides revising...",
        "💥 Round {n}: Neither is backing down. Sharpening positions...",
        "🗡️  Round {n}: Going for the jugular...",
        "🌪️  Round {n}: The debate intensifies...",
    ]
    max_rounds = rounds + 2  # allow up to 2 auto-extensions
    round_num = 0
    while round_num < max_rounds:
        round_num += 1
        msg = adversarial_round_msgs[(round_num - 1) % len(adversarial_round_msgs)].format(n=round_num)
        _progress(f"\n{msg}")
        _progress("__FIGHT_START__")
        _angel_rev_sys = DEBATE_ANGEL_SYSTEM.format(
            previous_round=f"The Critic's argument:\n{devil_pos}"
        )
        _devil_rev_sys = DEBATE_DEVIL_SYSTEM.format(
            previous_round=f"The Advocate's argument:\n{angel_pos}"
        )
        if template:
            _angel_rev_sys += f"\n\nDecision context: {template.debater_context}"
            _devil_rev_sys += f"\n\nDecision context: {template.debater_context}"
        if research_context:
            _angel_rev_sys += f"\n\n{research_context}\n\nCite specific sources when making claims."
            _devil_rev_sys += f"\n\n{research_context}\n\nCite specific sources when making claims."
        angel_task = call_model(angel_model, [
            {"role": "system", "content": _angel_rev_sys},
            {"role": "user", "content": query},
        ], timeout=DEBATE_TIMEOUT_SECONDS)
        devil_task = call_model(devil_model, [
            {"role": "system", "content": _devil_rev_sys},
            {"role": "user", "content": query},
        ], timeout=DEBATE_TIMEOUT_SECONDS)

        angel_r, devil_r = await asyncio.gather(angel_task, devil_task)
        _progress("__FIGHT_STOP__")

        if angel_r:
            angel_pos = angel_r["content"]
            _update_cost(cost, angel_r)
            model_status[f"👼 {angel_short}"] = f"✅ R{round_num}:{angel_r['latency_s']}s"
        if devil_r:
            devil_pos = devil_r["content"]
            _update_cost(cost, devil_r)
            model_status[f"😈 {devil_short}"] = f"✅ R{round_num}:{devil_r['latency_s']}s"

        all_rounds.append({"angel": angel_pos, "devil": devil_pos})

        # Show how positions evolved — thesis, not a wall of text
        angel_rev = _best_sentence(angel_pos)
        devil_rev = _best_sentence(devil_pos)
        _progress(f"   👼 \"{angel_rev}\"")
        _progress(f"   😈 \"{devil_rev}\"")

        # Convergence check with momentum detection
        agreement = compute_agreement([angel_pos, devil_pos])
        score = agreement["score"]
        delta = abs(score - prev_agreement_score)

        # Visual agreement bar
        filled = int(score * 20)
        bar = "█" * filled + "░" * (20 - filled)
        _progress(f"   [{bar}] {score:.0%} agreement")

        if score > 0.7:
            converged_at = round_num
            _progress(f"   🤝 They're... agreeing? Debate over.")
            break
        elif round_num >= rounds and delta < 0.03:
            # Positions ossified — no point continuing
            _progress(f"   🪨 Positions hardened (Δ{delta:.0%}). Neither will budge.")
            break
        elif round_num >= rounds and delta >= 0.03 and round_num < max_rounds:
            # Still shifting — auto-extend
            _progress(f"   🔄 Still shifting (Δ{delta:.0%}) — extending debate...")
        elif round_num >= max_rounds:
            _progress(f"   ⏰ Max rounds reached.")
            break

        prev_agreement_score = score

    # ── Final judgment ─────────────────────────────────────────────────────
    total_rounds = len(all_rounds) - 1  # subtract opening
    _progress(f"\n{'─' * 40}")
    _progress(f"⚖️  JUDGE ENTERS ({total_rounds} rounds of testimony)")
    _progress(f"{'─' * 40}")
    aggregator = get_aggregator(prefer_premium=True)
    elapsed = int((time.monotonic() - start) * 1000)

    if not aggregator:
        return {
            "response": f"**Advocate:**\n{angel_pos}\n\n---\n\n**Critic:**\n{devil_pos}",
            "rounds": all_rounds, "model_status": model_status,
            "cost": cost, "latency_ms": elapsed, "converged_at": converged_at,
        }

    _progress("__JUDGE_START__")
    _judge_system = DEBATE_ADVERSARIAL_JUDGE_SYSTEM.format(
        angel_position=angel_pos, devil_position=devil_pos
    )
    # Template: full structured criteria for the judge
    if template:
        _judge_system += f"\n\n{template.judge_addendum}"
    if research_context:
        _judge_system += (
            "\n\nThe following research was provided to both sides. "
            "Verify that cited claims match the sources. Flag any claims "
            "that aren't supported by the research.\n\n" + research_context
        )
    judge_result = await call_model(
        aggregator,
        [
            {"role": "system", "content": _judge_system},
            {"role": "user", "content": query},
        ],
        temperature=0.1,
        timeout=AGGREGATOR_TIMEOUT_SECONDS,
    )
    _progress("__JUDGE_STOP__")

    elapsed = int((time.monotonic() - start) * 1000)
    if judge_result:
        _update_cost(cost, judge_result, is_aggregator=True)

    # Extract source URLs from research context
    research_sources = []
    if research_context:
        for line in research_context.split("\n"):
            if line.startswith("Source: http"):
                research_sources.append(line.replace("Source: ", "").strip())

    return {
        "response": judge_result["content"] if judge_result else angel_pos,
        "rounds": all_rounds,
        "model_status": model_status,
        "cost": cost,
        "latency_ms": elapsed,
        "converged_at": converged_at,
        "debate_style": "adversarial",
        "research_grounded": bool(research_context),
        "research_sources": research_sources,
        "research_context": research_context,
        "query": query,
        "angel_model": angel_short,
        "devil_model": devil_short,
        "template": template.name if template else None,
    }

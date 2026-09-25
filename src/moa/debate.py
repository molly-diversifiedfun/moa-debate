"""Multi-round debate: peer and adversarial (angel/devil/judge) patterns.

Adversarial debates use a composable pipeline:
  resolve_template → select_models → research → opening → rounds → judge → format_result

Each stage is an async function: stage(state) -> state
The DebateState dataclass carries all context between stages.
"""

import asyncio
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable

from .config import DEBATE_TIMEOUT_SECONDS, AGGREGATOR_TIMEOUT_SECONDS
from .budget import record_spend
from .models import (
    ModelConfig, QueryCost, TIERS, get_aggregator,
)
from .prompts import (
    DEBATE_ROUND_SYSTEM, DEBATE_JUDGE_SYSTEM, STRATEGIC_ADDENDUM,
    format_proposals,
    DEBATE_CHALLENGE_SYSTEM, DEBATE_REVISION_WITH_CHALLENGES_SYSTEM,
    DEBATE_ANGEL_SYSTEM, DEBATE_DEVIL_SYSTEM, DEBATE_ADVERSARIAL_JUDGE_SYSTEM,
)
from .orchestrator import call_model, _check_budget_or_raise, _update_cost, compute_agreement
from . import events as ev


# ════════���═════════════════════════════════════════════════════════════════════
#  DEBATE STATE — flows through the pipeline
# ══════════════════════════════════════════���═════════════════════════════���═════

@dataclass
class DebateState:
    """Immutable-ish state that flows through each pipeline stage."""
    # Input
    query: str
    rounds: int = 2
    tier_name: str = "pro"
    template_name: Optional[str] = None
    on_progress: Callable = field(default=lambda msg: None, repr=False)

    # Resolved by stages
    template: Any = None  # Optional[DecisionTemplate]
    angel_model: Optional[ModelConfig] = None
    devil_model: Optional[ModelConfig] = None
    research_context: str = ""
    angel_pos: str = ""
    devil_pos: str = ""
    all_rounds: List[Dict] = field(default_factory=list)
    converged_at: Optional[int] = None
    judge_response: str = ""

    # Tracking
    cost: Optional[QueryCost] = None
    model_status: Dict[str, str] = field(default_factory=dict)
    start_time: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  PEER DEBATE STATE — flows through the peer pipeline
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PeerDebateState:
    """Mutable state that flows through peer debate pipeline stages."""
    # Input
    query: str
    rounds: int = 2
    tier_name: str = "pro"
    on_progress: Callable = field(default=lambda msg: None, repr=False)

    # Resolved by stages
    available_models: List[ModelConfig] = field(default_factory=list)
    current_positions: Dict[str, str] = field(default_factory=dict)
    challenges_by_model: Dict[str, str] = field(default_factory=dict)
    all_rounds: List[Dict] = field(default_factory=list)
    converged_at: Optional[int] = None
    judge_response: str = ""

    # Tracking
    cost: Optional[QueryCost] = None
    model_status: Dict[str, str] = field(default_factory=dict)
    start_time: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  PEER PIPELINE STAGES
# ══════════════════════════════════════════════════════════════════════════════

async def peer_select_models(state: PeerDebateState) -> PeerDebateState:
    """Stage 1: Pick models from the requested tier."""
    tier = TIERS.get(state.tier_name)
    if not tier:
        raise ValueError(f"Unknown tier: {state.tier_name}")

    state.available_models = tier.available_proposers
    if len(state.available_models) < 2:
        raise RuntimeError("Debate requires at least 2 available models.")

    names = [_short_name(m) for m in state.available_models]
    state.on_progress(ev.peer_independent(len(state.available_models), names))
    return state


async def peer_independent(state: PeerDebateState) -> PeerDebateState:
    """Stage 2: All models form independent opinions (Round 0)."""
    tasks = [
        call_model(m, [{"role": "user", "content": state.query}])
        for m in state.available_models
    ]
    results = await asyncio.gather(*tasks)

    for model, result in zip(state.available_models, results):
        short = _short_name(model)
        if result:
            state.current_positions[model.name] = result["content"]
            _update_cost(state.cost, result)
            state.model_status[short] = f"✅ R0:{result['latency_s']}s"
        else:
            state.model_status[short] = "❌ failed R0"

    state.all_rounds.append(dict(state.current_positions))

    if len(state.current_positions) < 2:
        raise RuntimeError("Less than 2 models responded. Cannot debate.")

    return state


async def peer_challenge(state: PeerDebateState) -> PeerDebateState:
    """Stage 3: Models find flaws in each other's responses."""
    state.on_progress(ev.peer_challenge())

    challenge_tasks = []
    challenge_models = []

    for model in state.available_models:
        if model.name not in state.current_positions:
            continue
        others = {k: v for k, v in state.current_positions.items() if k != model.name}
        if not others:
            continue

        other_text = format_proposals(
            list(others.values()),
            [k.split("/")[-1] for k in others.keys()]
        )
        challenge_tasks.append(
            call_model(model, [
                {"role": "system", "content": DEBATE_CHALLENGE_SYSTEM.format(other_responses=other_text)},
                {"role": "user", "content": state.query},
            ])
        )
        challenge_models.append(model)

    challenge_results = await asyncio.gather(*challenge_tasks)
    for model, result in zip(challenge_models, challenge_results):
        short = _short_name(model)
        if result:
            state.challenges_by_model[model.name] = result["content"]
            _update_cost(state.cost, result)
            state.model_status[short] = f"✅ CH:{result['latency_s']}s"

    return state


async def peer_revision_rounds(state: PeerDebateState) -> PeerDebateState:
    """Stage 4: Models revise positions, with convergence checking."""
    round_messages = [
        "⚔️  Round {n}: Models read the challenges. Egos bruised. Revising...",
        "🔄 Round {n}: \"Actually, you make a fair point...\" (or not)",
        "🤔 Round {n}: Models reconsider. Some dig in. Some fold.",
    ]

    for round_num in range(1, state.rounds + 1):
        msg = round_messages[(round_num - 1) % len(round_messages)].format(n=round_num)
        state.on_progress(ev.peer_revision(round_num, msg))

        revision_tasks = []
        revision_models = []

        for model in state.available_models:
            if model.name not in state.current_positions:
                continue
            others = {k: v for k, v in state.current_positions.items() if k != model.name}
            if not others:
                continue

            other_text = format_proposals(
                list(others.values()),
                [k.split("/")[-1] for k in others.keys()]
            )

            # First revision round: include challenges
            if round_num == 1 and state.challenges_by_model:
                relevant_challenges = {
                    k: v for k, v in state.challenges_by_model.items() if k != model.name
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
                    {"role": "user", "content": state.query},
                ])
            )
            revision_models.append(model)

        results = await asyncio.gather(*revision_tasks)
        for model, result in zip(revision_models, results):
            short = _short_name(model)
            if result:
                state.current_positions[model.name] = result["content"]
                _update_cost(state.cost, result)
                state.model_status[short] = f"✅ R{round_num}:{result['latency_s']}s"

        state.all_rounds.append(dict(state.current_positions))

        # Convergence check
        agreement = compute_agreement(list(state.current_positions.values()))
        score = agreement["score"]
        state.on_progress(ev.peer_agreement(score))

        if score > 0.7:
            state.converged_at = round_num
            state.on_progress(ev.peer_converged(round_num, score))
            break
        else:
            state.on_progress(ev.peer_no_consensus(score))

    return state


async def peer_judge(state: PeerDebateState) -> PeerDebateState:
    """Stage 5: Judge synthesizes all positions into a final verdict."""
    state.on_progress(ev.peer_judge())

    aggregator = get_aggregator(prefer_premium=True)
    if not aggregator:
        state.judge_response = list(state.current_positions.values())[0]
        return state

    final_text = format_proposals(
        list(state.current_positions.values()),
        [k.split("/")[-1] for k in state.current_positions.keys()]
    )
    judge_result = await call_model(
        aggregator,
        [
            {"role": "system", "content": DEBATE_JUDGE_SYSTEM.format(final_positions=final_text) + STRATEGIC_ADDENDUM},
            {"role": "user", "content": state.query},
        ],
        temperature=0.1,
        timeout=AGGREGATOR_TIMEOUT_SECONDS,
    )

    if judge_result:
        _update_cost(state.cost, judge_result, is_aggregator=True)
        state.judge_response = judge_result["content"]
    else:
        state.judge_response = list(state.current_positions.values())[0]

    return state


def peer_format_result(state: PeerDebateState) -> Dict[str, Any]:
    """Assemble final result dict for peer debate."""
    elapsed = int((time.monotonic() - state.start_time) * 1000)
    return {
        "response": state.judge_response,
        "rounds": state.all_rounds,
        "model_status": state.model_status,
        "cost": state.cost,
        "latency_ms": elapsed,
        "converged_at": state.converged_at,
        "debate_style": "peer",
    }


# Default peer pipeline
PEER_PIPELINE = [peer_select_models, peer_independent, peer_challenge, peer_revision_rounds, peer_judge]


async def run_peer_pipeline(
    query: str,
    rounds_count: int = 2,
    tier_name: str = "pro",
    on_progress: Optional[Callable] = None,
    pipeline: Optional[List[Callable]] = None,
) -> Dict[str, Any]:
    """Run peer debate as a composable pipeline."""
    _check_budget_or_raise()

    state = PeerDebateState(
        query=query,
        rounds=rounds_count,
        tier_name=tier_name,
        on_progress=on_progress or (lambda msg: None),
        cost=QueryCost(tier=f"peer-{tier_name}"),
        start_time=time.monotonic(),
    )

    stages = pipeline or PEER_PIPELINE
    for stage_fn in stages:
        state = await stage_fn(state)

    return peer_format_result(state)


# ══════════════════════════════════════════════════════════════════════════════
#  ADVERSARIAL PIPELINE STAGES — each takes state, returns state
# ══════════════════════════════════════════════════════════════════════════════

async def resolve_template(state: DebateState) -> DebateState:
    """Stage 1: Resolve debate template from name or auto-detect."""
    from .templates import get_template, detect_template

    if state.template_name:
        state.template = get_template(state.template_name)
        if state.template:
            state.on_progress(ev.template_resolved(state.template.name, state.template.description))
        else:
            state.on_progress(ev.template_unknown(state.template_name))
    else:
        state.template = detect_template(state.query)
        if state.template:
            state.on_progress(ev.template_resolved(state.template.name, state.template.description, auto_detected=True))

    return state


async def select_models(state: DebateState) -> DebateState:
    """Stage 2: Pick the strongest healthy angel/devil models across all tiers."""
    from .models import available_models as get_all_available
    from .health import should_skip

    tier = TIERS.get(state.tier_name)
    if not tier:
        raise ValueError(f"Unknown tier: {state.tier_name}")

    all_available = get_all_available()
    healthy = [m for m in all_available if not should_skip(m.name)]
    if len(healthy) < 2:
        healthy = all_available
    if len(healthy) < 2:
        raise RuntimeError("Adversarial debate requires at least 2 available models.")

    # Sort by capability (output cost as proxy)
    ranked = sorted(healthy, key=lambda m: m.output_cost_per_mtok, reverse=True)
    state.angel_model = ranked[0]
    # Devil must be from a DIFFERENT provider for genuine diversity
    state.devil_model = next(
        (m for m in ranked[1:] if m.provider != state.angel_model.provider),
        ranked[1],
    )

    # Log skipped unhealthy models
    all_ranked = sorted(all_available, key=lambda m: m.output_cost_per_mtok, reverse=True)
    if all_ranked[0].name != state.angel_model.name or (len(all_ranked) > 1 and all_ranked[1].name != state.devil_model.name):
        skipped_names = [m.name.split("/")[-1] for m in all_ranked if should_skip(m.name)]
        if skipped_names:
            state.on_progress(ev.skipped_unhealthy(skipped_names))

    return state


async def research(state: DebateState) -> DebateState:
    """Stage 3: Ground the debate in real web sources."""
    try:
        from .research import get_all_providers, format_research_context
        providers = get_all_providers()
        if not providers:
            state.on_progress(ev.research_unavailable())
            return state

        provider_names = [type(p).__name__.replace("Provider", "") for p in providers]
        state.on_progress(ev.research_start(provider_names))

        all_results: list = []
        seen_urls: set = set()
        search_queries = [
            state.query,
            f"arguments for {state.query}",
            f"arguments against {state.query}",
            f"{state.query} evidence research data",
        ]
        if state.template:
            search_queries.extend(state.template.research_queries)

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
            if len(all_results) >= 6:
                break

        if all_results:
            from .config import RESEARCH_CONTEXT_MAX_CHARS_DEEP
            state.research_context = format_research_context(all_results, max_chars=RESEARCH_CONTEXT_MAX_CHARS_DEEP)

        source_count = state.research_context.count("Source: http") if state.research_context else 0
        state.on_progress(ev.research_complete(source_count))
    except Exception:
        pass  # research is best-effort

    return state


async def opening(state: DebateState) -> DebateState:
    """Stage 4: Angel and devil form their opening arguments."""
    angel_short = _short_name(state.angel_model)
    devil_short = _short_name(state.devil_model)

    # Battle card
    _render_battle_card(state.on_progress, angel_short, devil_short)

    # Build system prompts
    angel_system = DEBATE_ANGEL_SYSTEM.format(previous_round="This is your opening argument.")
    devil_system = DEBATE_DEVIL_SYSTEM.format(previous_round="This is your opening argument.")
    if state.template:
        angel_system += f"\n\nDecision context: {state.template.debater_context}"
        devil_system += f"\n\nDecision context: {state.template.debater_context}"
    if state.research_context:
        cite_instruction = "\n\nCite specific sources from the research when making claims. Reference data, studies, or examples by name."
        angel_system += f"\n\n{state.research_context}{cite_instruction}"
        devil_system += f"\n\n{state.research_context}{cite_instruction}"

    state.on_progress(ev.fight_start())
    angel_r, devil_r = await asyncio.gather(
        call_model(state.angel_model, [
            {"role": "system", "content": angel_system},
            {"role": "user", "content": state.query},
        ], timeout=DEBATE_TIMEOUT_SECONDS),
        call_model(state.devil_model, [
            {"role": "system", "content": devil_system},
            {"role": "user", "content": state.query},
        ], timeout=DEBATE_TIMEOUT_SECONDS),
    )
    state.on_progress(ev.fight_stop())

    state.angel_pos = angel_r["content"] if angel_r else ""
    state.devil_pos = devil_r["content"] if devil_r else ""

    if angel_r:
        _update_cost(state.cost, angel_r)
        state.model_status[f"👼 {angel_short}"] = f"✅ R0:{angel_r['latency_s']}s"
    else:
        state.model_status[f"👼 {angel_short}"] = "❌ failed R0"
    if devil_r:
        _update_cost(state.cost, devil_r)
        state.model_status[f"😈 {devil_short}"] = f"✅ R0:{devil_r['latency_s']}s"
    else:
        state.model_status[f"😈 {devil_short}"] = "❌ failed R0"

    # Fallback if one side failed
    if not state.angel_pos or not state.devil_pos:
        from .models import available_models as get_all_available
        ranked = sorted(get_all_available(), key=lambda m: m.output_cost_per_mtok, reverse=True)
        remaining = [m for m in ranked[2:] if m.available] if len(ranked) > 2 else []
        if not state.angel_pos and remaining:
            state.angel_model = remaining[0]
            angel_short = _short_name(state.angel_model)
            fb = await call_model(state.angel_model, [
                {"role": "system", "content": DEBATE_ANGEL_SYSTEM.format(previous_round="This is your opening argument.")},
                {"role": "user", "content": state.query},
            ])
            if fb:
                state.angel_pos = fb["content"]
                _update_cost(state.cost, fb)
                state.model_status[f"👼 {angel_short}"] = f"✅ R0:{fb['latency_s']}s (fallback)"
        if not state.devil_pos and remaining:
            fb_model = remaining[-1] if len(remaining) > 1 else remaining[0]
            devil_short_fb = _short_name(fb_model)
            if fb_model.name != state.angel_model.name if not state.angel_pos else True:
                fb = await call_model(fb_model, [
                    {"role": "system", "content": DEBATE_DEVIL_SYSTEM.format(previous_round="This is your opening argument.")},
                    {"role": "user", "content": state.query},
                ])
                if fb:
                    state.devil_pos = fb["content"]
                    state.devil_model = fb_model
                    _update_cost(state.cost, fb)
                    state.model_status[f"😈 {devil_short_fb}"] = f"✅ R0:{fb['latency_s']}s (fallback)"

    if not state.angel_pos or not state.devil_pos:
        raise RuntimeError(
            "Adversarial debate requires 2 responding models. "
            "Available models may be rate-limited or unavailable."
        )

    state.all_rounds.append({"angel": state.angel_pos, "devil": state.devil_pos})

    # Show opening theses
    state.on_progress(ev.argument_preview("angel", _best_sentence(state.angel_pos), _word_count(state.angel_pos)))
    state.on_progress(ev.argument_preview("devil", _best_sentence(state.devil_pos), _word_count(state.devil_pos)))

    return state


async def rounds(state: DebateState) -> DebateState:
    """Stage 5: Revision rounds with convergence detection and auto-extension."""
    angel_short = _short_name(state.angel_model)
    devil_short = _short_name(state.devil_model)

    prev_agreement_score = compute_agreement([state.angel_pos, state.devil_pos])["score"]
    state.on_progress(ev.opening_agreement(prev_agreement_score))

    round_msgs = [
        "⚔️  Round {n}: They've read each other's arguments. Gloves are off.",
        "🔥 Round {n}: \"That's your best argument?\" Both sides revising...",
        "💥 Round {n}: Neither is backing down. Sharpening positions...",
        "🗡️  Round {n}: Going for the jugular...",
        "🌪️  Round {n}: The debate intensifies...",
    ]
    max_rounds = state.rounds + 2  # allow up to 2 auto-extensions
    round_num = 0
    while round_num < max_rounds:
        round_num += 1
        msg = round_msgs[(round_num - 1) % len(round_msgs)].format(n=round_num)
        state.on_progress(ev.round_start(round_num, msg))
        state.on_progress(ev.fight_start())

        _angel_rev_sys = DEBATE_ANGEL_SYSTEM.format(
            previous_round=f"The Critic's argument:\n{state.devil_pos}"
        )
        _devil_rev_sys = DEBATE_DEVIL_SYSTEM.format(
            previous_round=f"The Advocate's argument:\n{state.angel_pos}"
        )
        if state.template:
            _angel_rev_sys += f"\n\nDecision context: {state.template.debater_context}"
            _devil_rev_sys += f"\n\nDecision context: {state.template.debater_context}"
        if state.research_context:
            _angel_rev_sys += f"\n\n{state.research_context}\n\nCite specific sources when making claims."
            _devil_rev_sys += f"\n\n{state.research_context}\n\nCite specific sources when making claims."

        angel_r, devil_r = await asyncio.gather(
            call_model(state.angel_model, [
                {"role": "system", "content": _angel_rev_sys},
                {"role": "user", "content": state.query},
            ], timeout=DEBATE_TIMEOUT_SECONDS),
            call_model(state.devil_model, [
                {"role": "system", "content": _devil_rev_sys},
                {"role": "user", "content": state.query},
            ], timeout=DEBATE_TIMEOUT_SECONDS),
        )
        state.on_progress(ev.fight_stop())

        if angel_r:
            state.angel_pos = angel_r["content"]
            _update_cost(state.cost, angel_r)
            state.model_status[f"👼 {angel_short}"] = f"✅ R{round_num}:{angel_r['latency_s']}s"
        if devil_r:
            state.devil_pos = devil_r["content"]
            _update_cost(state.cost, devil_r)
            state.model_status[f"😈 {devil_short}"] = f"✅ R{round_num}:{devil_r['latency_s']}s"

        state.all_rounds.append({"angel": state.angel_pos, "devil": state.devil_pos})

        # Show evolved theses
        state.on_progress(ev.round_thesis("angel", _best_sentence(state.angel_pos)))
        state.on_progress(ev.round_thesis("devil", _best_sentence(state.devil_pos)))

        # Convergence check with momentum detection
        agreement = compute_agreement([state.angel_pos, state.devil_pos])
        score = agreement["score"]
        delta = abs(score - prev_agreement_score)

        state.on_progress(ev.agreement_bar(score))

        if score > 0.7:
            state.converged_at = round_num
            state.on_progress(ev.converged(round_num))
            break
        elif round_num >= state.rounds and delta < 0.03:
            state.on_progress(ev.hardened(delta))
            break
        elif round_num >= state.rounds and delta >= 0.03 and round_num < max_rounds:
            state.on_progress(ev.extended(delta))
        elif round_num >= max_rounds:
            state.on_progress(ev.max_rounds())
            break

        prev_agreement_score = score

    return state


async def judge(state: DebateState) -> DebateState:
    """Stage 6: Judge synthesizes both perspectives into a verdict."""
    angel_short = _short_name(state.angel_model)
    devil_short = _short_name(state.devil_model)
    total_rounds = len(state.all_rounds) - 1

    state.on_progress(ev.judge_enter(total_rounds))

    aggregator = get_aggregator(prefer_premium=True)
    if not aggregator:
        state.judge_response = f"**Advocate:**\n{state.angel_pos}\n\n---\n\n**Critic:**\n{state.devil_pos}"
        return state

    state.on_progress(ev.judge_start())
    _judge_system = DEBATE_ADVERSARIAL_JUDGE_SYSTEM.format(
        angel_position=state.angel_pos, devil_position=state.devil_pos
    )
    if state.template:
        _judge_system += f"\n\n{state.template.judge_addendum}"
    if state.research_context:
        _judge_system += (
            "\n\nThe following research was provided to both sides. "
            "Verify that cited claims match the sources. Flag any claims "
            "that aren't supported by the research.\n\n" + state.research_context
        )

    judge_result = await call_model(
        aggregator,
        [
            {"role": "system", "content": _judge_system},
            {"role": "user", "content": state.query},
        ],
        temperature=0.1,
        timeout=AGGREGATOR_TIMEOUT_SECONDS,
    )
    state.on_progress(ev.judge_stop())

    if judge_result:
        _update_cost(state.cost, judge_result, is_aggregator=True)
        state.judge_response = judge_result["content"]
    else:
        state.judge_response = state.angel_pos

    return state


def format_result(state: DebateState) -> Dict[str, Any]:
    """Stage 7: Assemble the final result dict."""
    elapsed = int((time.monotonic() - state.start_time) * 1000)

    research_sources = []
    if state.research_context:
        for line in state.research_context.split("\n"):
            if line.startswith("Source: http"):
                research_sources.append(line.replace("Source: ", "").strip())

    return {
        "response": state.judge_response,
        "rounds": state.all_rounds,
        "model_status": state.model_status,
        "cost": state.cost,
        "latency_ms": elapsed,
        "converged_at": state.converged_at,
        "debate_style": "adversarial",
        "research_grounded": bool(state.research_context),
        "research_sources": research_sources,
        "research_context": state.research_context,
        "query": state.query,
        "angel_model": _short_name(state.angel_model) if state.angel_model else None,
        "devil_model": _short_name(state.devil_model) if state.devil_model else None,
        "template": state.template.name if state.template else None,
    }


# ���═══════════════════════════════════���═════════════════════════════════════════
#  PIPELINE RUNNER
# ═════���══════════════���══════════════════════════════════���══════════════════════

# Default adversarial pipeline
ADVERSARIAL_PIPELINE = [resolve_template, select_models, research, opening, rounds, judge]


async def run_adversarial_pipeline(
    query: str,
    rounds_count: int = 2,
    tier_name: str = "pro",
    on_progress: Optional[Callable] = None,
    template_name: Optional[str] = None,
    pipeline: Optional[List[Callable]] = None,
) -> Dict[str, Any]:
    """Run the adversarial debate as a composable pipeline.

    Each stage in the pipeline is an async function: stage(state) -> state.
    Override `pipeline` to customize, skip, or reorder stages.
    """
    _check_budget_or_raise()

    state = DebateState(
        query=query,
        rounds=rounds_count,
        tier_name=tier_name,
        template_name=template_name,
        on_progress=on_progress or (lambda msg: None),
        cost=QueryCost(tier=f"adversarial-{tier_name}"),
        start_time=time.monotonic(),
    )

    stages = pipeline or ADVERSARIAL_PIPELINE
    for stage_fn in stages:
        state = await stage_fn(state)

    return format_result(state)


# ��═════════════════════════════���═══════════════════════════════════════════════
#  PUBLIC API — peer debate (unchanged) + adversarial (now uses pipeline)
# ══════���═══════════════════════════════════════════════════════════════════════

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
      Uses composable pipeline: resolve_template → select_models → research →
      opening ��� rounds → judge → format_result
    """
    _progress = on_progress or (lambda msg: None)

    if debate_style == "adversarial":
        return await run_adversarial_pipeline(
            query, rounds_count=rounds, tier_name=tier_name,
            on_progress=_progress, template_name=template_name,
        )

    return await run_peer_pipeline(
        query, rounds_count=rounds, tier_name=tier_name,
        on_progress=_progress,
    )





# ═���════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════���════════════════════════════════════════════════════════════════════════

def _short_name(model: ModelConfig) -> str:
    """Extract short model name from full LiteLLM identifier."""
    return model.name.split("/")[-1] if "/" in model.name else model.name


def _dw(s: str) -> int:
    """Terminal display width — handles emoji vs ASCII correctly."""
    w = 0
    for i, c in enumerate(s):
        cp = ord(c)
        if cp == 0xFE0F:
            w += 1
            continue
        eaw = unicodedata.east_asian_width(c)
        if eaw in ("W", "F") or cp > 0x1F000:
            w += 2
        else:
            w += 1
    return w


def _render_battle_card(on_progress: Callable, angel_short: str, devil_short: str):
    """Render the adversarial debate battle card."""
    _label_advocate = f"Advocate: {angel_short}"
    _label_critic   = f"Critic:   {devil_short}"
    _adv_content = f"  👼 {_label_advocate}"
    _crt_content = f"  😈 {_label_critic}"
    _title_text  = "⚔️  ADVERSARIAL DEBATE  ⚔️"
    _quote       = '"Let them fight."'
    _quote_content = f"  {_quote}"
    _inner = max(_dw(_adv_content), _dw(_crt_content), _dw(_title_text), _dw(_quote_content)) + 4
    _top    = "╔" + "═" * _inner + "╗"
    _bottom = "╚" + "═" * _inner + "╝"
    _blank  = "║" + " " * _inner + "║"

    def _pad_line(content: str) -> str:
        return "║" + content + " " * (_inner - _dw(content)) + "║"

    def _center_line(content: str) -> str:
        pad = _inner - _dw(content)
        left = pad // 2
        right = pad - left
        return "║" + " " * left + content + " " * right + "║"

    on_progress(
        f"{_top}\n"
        f"{_center_line(_title_text)}\n"
        f"{_blank}\n"
        f"{_pad_line(_adv_content)}\n"
        f"{_pad_line(_crt_content)}\n"
        f"{_blank}\n"
        f"{_center_line(_quote_content)}\n"
        f"{_bottom}"
    )


# ── Best sentence extraction for debate previews ──────────────────────────────

_SKIP_PREFIXES = (
    "i need to", "let me", "as the advocate", "as the critic",
    "as your advocate", "i'll build", "i want to", "to answer this",
    "this is a", "here's my", "my argument", "i'm going to",
    "opening argument", "the evidence strongly", "the strongest argument",
)
_SPECIFICITY_SIGNALS = [
    "%", "$", "study", "research", "data", "evidence", "found that",
    "showed", "according", "published", "trial", "patients", "users",
    "companies", "however", "concede", "but", "critical", "risk",
    "failure", "success", "rate", "year", "month", "week",
]


def _best_sentence(text: str) -> str:
    """Find the most specific, interesting sentence — not the opening."""
    sentences = re.split(r'(?<=[.!?])\s+', text.replace("\n", " ").strip())
    scored = []
    for s in sentences:
        stripped = s.strip().lstrip("#*-– ")
        if len(stripped) < 20 or len(stripped) > 250:
            continue
        lower = stripped.lower()
        if lower.startswith(_SKIP_PREFIXES):
            continue
        score = sum(1 for sig in _SPECIFICITY_SIGNALS if sig in lower)
        score += len(re.findall(r'\d+', stripped))
        scored.append((score, stripped))
    if not scored:
        for s in sentences:
            stripped = s.strip().lstrip("#*-– ")
            if len(stripped) >= 20 and not stripped.lower().startswith(_SKIP_PREFIXES):
                return stripped[:200]
        return text.replace("\n", " ").strip()[:150]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1][:200]


def _word_count(text: str) -> int:
    return len(text.split())

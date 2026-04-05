"""Expert Panel code review with specialized reviewers."""

import asyncio
import time
from typing import List, Dict, Any

from .config import AGGREGATOR_TIMEOUT_SECONDS, MAX_DIFF_CHARS
from .models import QueryCost, REVIEWER_ROLES, get_aggregator
from .prompts import (
    CODE_REVIEW_AGGREGATOR, format_review_findings,
    REVIEWER_DISCOURSE_SYSTEM,
)
from .orchestrator import call_model, _check_budget_or_raise, _update_cost


async def run_expert_review(
    diff: str,
    context: str = "",
    discourse: bool = False,
    roles: List = None,
) -> Dict[str, Any]:
    """Run Expert Panel code review with specialized reviewers.

    Default: Security + Architecture + Performance + Correctness -> Synthesizer
    With --personas: Fowler + Beck + Hickey + Metz -> Synthesizer
    With --discourse: adds a second round where reviewers react to each other
    """
    _check_budget_or_raise()

    cost = QueryCost(tier="expert-panel")
    start = time.monotonic()

    # Truncate oversized diffs
    diff_truncated = False
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS]
        diff_truncated = True

    review_prompt = f"Review this code change:\n\n{context}\n\n```diff\n{diff}\n```"

    review_roles = roles if roles is not None else REVIEWER_ROLES
    available_roles = []
    for role in review_roles:
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

    # ── Discourse round (optional) ─────────────────────────────────────────
    if discourse and len(findings) >= 2:
        discourse_tasks = []
        discourse_roles_used = []

        for i, finding in enumerate(findings):
            other_findings_text = "\n\n---\n\n".join(
                f"**{f['role']}:**\n{f['content']}"
                for j, f in enumerate(findings) if j != i
            )
            discourse_prompt = REVIEWER_DISCOURSE_SYSTEM.format(
                role=finding["role"],
                own_findings=finding["content"],
                other_findings=other_findings_text,
            )
            # Use same model that produced original finding
            role, model = available_roles[i]
            discourse_tasks.append(
                call_model(model, [
                    {"role": "system", "content": discourse_prompt},
                    {"role": "user", "content": f"React to other reviewers' findings on:\n```diff\n{diff[:2000]}\n```"},
                ])
            )
            discourse_roles_used.append((role, model))

        discourse_results = await asyncio.gather(*discourse_tasks)
        for (role, model), result in zip(discourse_roles_used, discourse_results):
            short = model.name.split("/")[-1] if "/" in model.name else model.name
            if result:
                findings.append({"role": f"{role.name} (discourse)", "content": result["content"]})
                _update_cost(cost, result)
                model_status[f"{role.name}:disc"] = f"✅ {result['latency_s']}s ({short})"

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
        model_status["→Synthesizer"] = f"✅ {synth_result['latency_s']}s ({agg_short})"

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

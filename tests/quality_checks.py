"""Quality-of-response checks for live debate/compare e2e tests.

Three layers:
  #1 Structural  — deterministic assertions about response format/content
  #2 Invariants  — pipeline-level properties (cost, evolution, diversity)
  #3 Rubric      — LLM-as-judge scoring (gated, costs ~$0.002/call)

Usage:
    from tests.quality_checks import assert_adversarial_quality, assert_peer_quality

    result = await run_adversarial_pipeline(...)
    assert_adversarial_quality(result, original_query="...")
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


# ══════════════════════════════════════════════════════════════════════════════
#  #1 STRUCTURAL CHECKS
# ══════════════════════════════════════════════════════════════════════════════

MIN_VERDICT_WORDS = 150
MAX_VERDICT_WORDS = 5000


def _words(text: str) -> int:
    return len(text.split())


def assert_nonempty(response: str, label: str = "response") -> None:
    assert response, f"{label} is empty"
    assert response.strip(), f"{label} is whitespace-only"


def assert_word_count_sane(response: str, label: str = "response") -> None:
    n = _words(response)
    assert n >= MIN_VERDICT_WORDS, f"{label} too short: {n} words (min {MIN_VERDICT_WORDS})"
    assert n <= MAX_VERDICT_WORDS, f"{label} suspiciously long: {n} words (max {MAX_VERDICT_WORDS})"


def assert_adversarial_format(verdict: str) -> None:
    """Adversarial judge verdicts must follow the prompts.py contract."""
    assert_nonempty(verdict, "adversarial verdict")
    assert_word_count_sane(verdict, "adversarial verdict")

    required_sections = [
        ("TL;DR", r"##\s*TL;DR"),
        ("Confidence", r"##\s*Confidence"),
        ("Case For", r"##\s*The Case For"),
        ("Case Against", r"##\s*The Case Against"),
        ("Decision Tree", r"##\s*Decision Tree"),
        ("Bottom Line", r"##\s*Bottom Line"),
    ]
    missing = [name for name, pattern in required_sections if not re.search(pattern, verdict, re.I)]
    assert not missing, f"adversarial verdict missing required sections: {missing}"


def assert_decision_tree_present(verdict: str) -> None:
    """Adversarial verdict must contain an ASCII decision tree."""
    has_tree = "├──" in verdict and "└──" in verdict
    assert has_tree, "decision tree chars (├── / └──) missing from adversarial verdict"

    # Check depth doesn't exceed 3 levels (count nested │ │   patterns)
    tree_lines = [l for l in verdict.split("\n") if any(c in l for c in "├└│")]
    max_depth = 0
    for line in tree_lines:
        # Count leading │ characters as depth indicators
        indent = len(line) - len(line.lstrip(" │"))
        depth = indent // 4  # rough heuristic
        max_depth = max(max_depth, depth)
    assert max_depth <= 4, f"decision tree too deep ({max_depth} levels, max 3)"


def extract_confidence(verdict: str) -> int | None:
    """Parse 'Confidence: X/10' from a verdict. Returns None if missing."""
    m = re.search(r"Confidence[:\s]*\[?(\d+)\s*/\s*10", verdict, re.I)
    if m:
        return int(m.group(1))
    return None


def assert_confidence_extractable(verdict: str) -> int:
    """Confidence score must be parseable and in [1, 10]."""
    conf = extract_confidence(verdict)
    assert conf is not None, "confidence score not extractable from verdict"
    assert 1 <= conf <= 10, f"confidence {conf} out of range [1, 10]"
    return conf


def assert_mentions_both_sides(verdict: str) -> None:
    """Adversarial judge must reference both advocate and critic positions."""
    lower = verdict.lower()
    has_advocate = any(w in lower for w in ["advocate", "case for", "pro ", "for:"])
    has_critic = any(w in lower for w in ["critic", "case against", "con ", "against"])
    assert has_advocate, "verdict does not mention advocate/case-for"
    assert has_critic, "verdict does not mention critic/case-against"


def assert_addresses_query(response: str, query: str, min_overlap: float = 0.15) -> None:
    """Response must share significant vocabulary with the original query.

    Crude but catches the 'generic preamble with no actual answer' failure.
    """
    import string
    stop = {
        "the", "a", "an", "is", "are", "to", "of", "in", "and", "or", "for",
        "should", "we", "i", "you", "be", "can", "will", "my", "this", "that",
        "it", "on", "at", "as", "with", "by", "do", "does", "if", "what",
    }

    def tokens(text: str) -> set:
        text = text.lower().translate(str.maketrans("", "", string.punctuation))
        return {w for w in text.split() if len(w) > 3 and w not in stop}

    q_tokens = tokens(query)
    r_tokens = tokens(response)
    if not q_tokens:
        return  # pathologically short query — nothing to check
    overlap = len(q_tokens & r_tokens) / len(q_tokens)
    assert overlap >= min_overlap, (
        f"response vocabulary overlap with query is {overlap:.0%} "
        f"(min {min_overlap:.0%}) — may not address the question"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  #2 PIPELINE INVARIANTS
# ══════════════════════════════════════════════════════════════════════════════

MAX_REASONABLE_COST_USD = {
    # Ceilings for peer debates (stays within requested tier).
    "flash": 0.02,
    "lite": 1.00,
    "pro": 3.00,
    "ultra": 6.00,
    # Adversarial picks strongest models across ALL tiers regardless of
    # requested `tier_name`, so real spend runs higher. A single Opus + GPT-5.4
    # adversarial round lands around $0.50-0.80.
}


def assert_cost_reasonable(result: Dict[str, Any], tier: str = "lite") -> None:
    """Cost must be >0 and below a sanity ceiling for the tier."""
    cost = result.get("cost")
    assert cost is not None, "no cost object in result"
    spent = cost.estimated_cost_usd
    assert spent > 0, f"cost is zero — did any model calls actually run? ({spent})"
    ceiling = MAX_REASONABLE_COST_USD.get(tier, 5.00)
    assert spent <= ceiling, f"cost ${spent:.4f} exceeds {tier} tier ceiling ${ceiling}"


def assert_rounds_evolved(rounds: List[Dict], min_delta: float = 0.15) -> None:
    """Positions must change between first and last round (models actually revised).

    Uses crude word-set delta. A peer debate that converges on round 1 still has
    different content between round 0 and round 1.
    """
    if len(rounds) < 2:
        return  # nothing to compare

    def flatten(r: Dict) -> str:
        return " ".join(str(v) for v in r.values())

    first = set(flatten(rounds[0]).lower().split())
    last = set(flatten(rounds[-1]).lower().split())
    if not first or not last:
        return
    delta = len(first.symmetric_difference(last)) / max(len(first | last), 1)
    assert delta >= min_delta, (
        f"rounds barely changed (delta {delta:.0%}, min {min_delta:.0%}) — "
        f"models may not be revising"
    )


def assert_models_diverse(model_status: Dict[str, str], min_successful: int = 2) -> None:
    """At least N models must have succeeded (no ❌ prefix)."""
    successful = [k for k, v in model_status.items() if "✅" in v]
    assert len(successful) >= min_successful, (
        f"only {len(successful)} models succeeded (min {min_successful}): {model_status}"
    )


def assert_adversarial_provider_diversity(result: Dict[str, Any]) -> None:
    """Adversarial debate must use models from different providers."""
    angel = result.get("angel_model", "")
    devil = result.get("devil_model", "")
    assert angel and devil, "adversarial result missing angel/devil model names"
    # Crude but effective: names typically include provider prefix or distinct tokens
    assert angel != devil, f"angel and devil are the same model: {angel}"


def assert_adversarial_quality(result: Dict[str, Any], original_query: str, tier: str = "lite") -> int:
    """Aggregate check: adversarial result meets all #1 + #2 quality gates.

    Returns the extracted confidence score so callers can make additional assertions.
    """
    verdict = result["response"]
    assert_adversarial_format(verdict)
    assert_decision_tree_present(verdict)
    confidence = assert_confidence_extractable(verdict)
    assert_mentions_both_sides(verdict)
    assert_addresses_query(verdict, original_query)

    assert_cost_reasonable(result, tier=tier)
    assert_rounds_evolved(result.get("rounds", []))
    assert_adversarial_provider_diversity(result)
    assert_models_diverse(result.get("model_status", {}))

    return confidence


def assert_peer_quality(result: Dict[str, Any], original_query: str, tier: str = "lite") -> None:
    """Aggregate check for peer debate results."""
    verdict = result["response"]
    assert_nonempty(verdict, "peer verdict")
    assert_word_count_sane(verdict, "peer verdict")
    assert_addresses_query(verdict, original_query)

    assert_cost_reasonable(result, tier=tier)
    assert_rounds_evolved(result.get("rounds", []))
    assert_models_diverse(result.get("model_status", {}))


# ══════════════════════════════════════════════════════════════════════════════
#  #3 LLM-AS-JUDGE RUBRIC — semantic quality scoring
# ══════════════════════════════════════════════════════════════════════════════

RUBRIC_PROMPT = """You are scoring an AI-generated decision verdict.

Original question: {query}

Verdict to score:
---
{verdict}
---

Score each dimension 1-5 (1=terrible, 5=excellent). Return ONLY valid JSON, no prose:

{{
  "answers_question": <1-5>,
  "considers_tradeoffs": <1-5>,
  "actionable": <1-5>,
  "specific_not_vague": <1-5>,
  "notes": "<one-sentence overall impression>"
}}

Scoring rubric:
- answers_question:   1=ignores the question, 3=partial, 5=directly answers
- considers_tradeoffs: 1=one-sided, 3=mentions both, 5=weighs them with judgment
- actionable:         1=pure analysis, 3=vague guidance, 5=concrete next steps
- specific_not_vague: 1=platitudes, 3=mixed, 5=numbers/examples/thresholds
"""

MIN_RUBRIC_SCORE = 3  # fail if any dimension scores <3


async def score_verdict_with_rubric(query: str, verdict: str) -> Dict[str, Any]:
    """Use a cheap model to score a verdict against the rubric.

    Returns parsed JSON dict. Raises on failure.
    """
    import json
    from moa.orchestrator import call_model
    from moa.models import GEMINI_FLASH, CLAUDE_HAIKU

    judge = GEMINI_FLASH if GEMINI_FLASH.available else CLAUDE_HAIKU
    if not judge.available:
        raise RuntimeError("No cheap judge model available for rubric scoring")

    prompt = RUBRIC_PROMPT.format(query=query, verdict=verdict[:4000])
    result = await call_model(
        judge,
        [{"role": "user", "content": prompt}],
        temperature=0.0,
        timeout=30,
    )
    assert result, "rubric judge call returned None"

    content = result["content"].strip()
    # Strip markdown code fences if present
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        scores = json.loads(content)
    except json.JSONDecodeError as e:
        raise AssertionError(f"rubric judge returned invalid JSON: {content[:300]}") from e

    return scores


def assert_rubric_scores_pass(scores: Dict[str, Any], min_score: int = MIN_RUBRIC_SCORE) -> None:
    """All numeric dimensions must meet min_score."""
    dimensions = ["answers_question", "considers_tradeoffs", "actionable", "specific_not_vague"]
    failures = []
    for dim in dimensions:
        val = scores.get(dim)
        assert val is not None, f"rubric missing dimension: {dim}"
        assert isinstance(val, (int, float)), f"{dim} is not numeric: {val!r}"
        if val < min_score:
            failures.append(f"{dim}={val}")
    assert not failures, (
        f"rubric scores below threshold {min_score}: {failures}. "
        f"Notes: {scores.get('notes', 'n/a')}"
    )

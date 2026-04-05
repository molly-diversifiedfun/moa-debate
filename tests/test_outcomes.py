"""Tests for outcome tracking system."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from moa.outcomes import (
    extract_confidence, log_debate, log_decision, tag_outcome,
    get_outcomes, compute_stats, _read_all,
)
from moa.models import QueryCost


# ── Confidence extraction ─────────────────────────────────────────────────────

def test_extract_confidence_standard():
    """Should extract 'Confidence: 7/10' pattern."""
    assert extract_confidence("## Confidence: 7/10\nSome text") == 7


def test_extract_confidence_bracketed():
    """Should extract 'Confidence: [8/10]' pattern."""
    assert extract_confidence("Confidence: [8/10]") == 8


def test_extract_confidence_inline():
    """Should extract '9/10 confidence' pattern."""
    assert extract_confidence("I rate this 9/10 confidence") == 9


def test_extract_confidence_missing():
    """Should return None when no confidence found."""
    assert extract_confidence("No confidence score here") is None


def test_extract_confidence_out_of_range():
    """Should reject values outside 1-10."""
    assert extract_confidence("Confidence: 0/10") is None
    assert extract_confidence("Confidence: 15/10") is None


def test_extract_confidence_boundary():
    """Should accept boundary values."""
    assert extract_confidence("Confidence: 1/10") == 1
    assert extract_confidence("Confidence: 10/10") == 10


# ── Outcome CRUD (using tmp files) ───────────────────────────────────────────

@pytest.fixture
def outcomes_file(tmp_path):
    """Patch OUTCOMES_FILE to use a temp file."""
    f = tmp_path / "outcomes.jsonl"
    with patch("moa.outcomes.OUTCOMES_FILE", f), \
         patch("moa.outcomes.MOA_HOME", tmp_path):
        yield f


def _make_result(**overrides):
    base = {
        "query": "Should we hire a senior engineer?",
        "response": "## TL;DR\nYes.\n\n## Confidence: 7/10\nGood evidence.",
        "debate_style": "adversarial",
        "template": "hire",
        "angel_model": "claude-opus",
        "devil_model": "gpt-5",
        "converged_at": 2,
        "research_grounded": True,
    }
    base.update(overrides)
    return base


def test_log_debate(outcomes_file):
    """log_debate should write an entry and return an ID."""
    result = _make_result()
    outcome_id = log_debate(result)
    assert outcome_id.startswith("debate-")

    entries = _read_all()
    assert len(entries) == 1
    assert entries[0]["query"] == "Should we hire a senior engineer?"
    assert entries[0]["confidence"] == 7
    assert entries[0]["template"] == "hire"
    assert entries[0]["decision"] is None
    assert entries[0]["outcome"] is None


def test_log_debate_no_confidence(outcomes_file):
    """log_debate should handle missing confidence gracefully."""
    result = _make_result(response="Just a verdict, no confidence score.")
    log_debate(result)
    entries = _read_all()
    assert entries[0]["confidence"] is None


def test_log_decision(outcomes_file):
    """log_decision should update the decision field."""
    outcome_id = log_debate(_make_result())
    assert log_decision(outcome_id, "Hired a senior engineer")

    entries = _read_all()
    assert entries[0]["decision"] == "Hired a senior engineer"


def test_log_decision_not_found(outcomes_file):
    """log_decision should return False for unknown ID."""
    assert log_decision("nonexistent-id", "decision") is False


def test_tag_outcome(outcomes_file):
    """tag_outcome should update outcome and result_tag."""
    outcome_id = log_debate(_make_result())
    assert tag_outcome(outcome_id, "Great hire, shipped 3 features", "good")

    entries = _read_all()
    assert entries[0]["outcome"] == "Great hire, shipped 3 features"
    assert entries[0]["result_tag"] == "good"
    assert entries[0]["outcome_ts"] is not None


def test_tag_outcome_invalid_tag(outcomes_file):
    """tag_outcome should default to 'unknown' for invalid tags."""
    outcome_id = log_debate(_make_result())
    tag_outcome(outcome_id, "meh", "invalid_tag")
    entries = _read_all()
    assert entries[0]["result_tag"] == "unknown"


# ── Filtering ─────────────────────────────────────────────────────────────────

def test_get_outcomes_all(outcomes_file):
    """get_outcomes should return all entries by default."""
    log_debate(_make_result())
    log_debate(_make_result(query="Second debate"))
    assert len(get_outcomes()) == 2


def test_get_outcomes_pending(outcomes_file):
    """get_outcomes(pending_only=True) should filter to untagged."""
    id1 = log_debate(_make_result())
    log_debate(_make_result(query="Second"))
    tag_outcome(id1, "Done", "good")

    pending = get_outcomes(pending_only=True)
    assert len(pending) == 1
    assert pending[0]["query"] == "Second"


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_compute_stats_empty(outcomes_file):
    """compute_stats should handle empty outcomes."""
    stats = compute_stats()
    assert stats["total_debates"] == 0
    assert stats["with_outcomes"] == 0


def test_compute_stats_with_data(outcomes_file):
    """compute_stats should compute accuracy correctly."""
    # 3 debates, 2 with outcomes
    id1 = log_debate(_make_result(template="hire"))
    id2 = log_debate(_make_result(template="hire", response="## Confidence: 9/10\nStrong"))
    log_debate(_make_result(template="build"))  # no outcome

    tag_outcome(id1, "Great", "good")
    tag_outcome(id2, "Bad hire", "bad")

    stats = compute_stats()
    assert stats["total_debates"] == 3
    assert stats["with_outcomes"] == 2
    assert stats["pending"] == 1
    assert stats["overall"]["correct"] == 1
    assert stats["overall"]["total"] == 2
    assert stats["overall"]["rate"] == 0.5

    # By template
    assert stats["by_template"]["hire"]["total"] == 2
    assert stats["by_template"]["hire"]["correct"] == 1


def test_compute_stats_by_confidence(outcomes_file):
    """compute_stats should bucket by confidence bracket."""
    id1 = log_debate(_make_result(response="## Confidence: 9/10\nHigh"))
    id2 = log_debate(_make_result(response="## Confidence: 3/10\nLow"))

    tag_outcome(id1, "Correct", "good")
    tag_outcome(id2, "Wrong", "bad")

    stats = compute_stats()
    assert stats["by_confidence"]["high (8-10)"]["correct"] == 1
    assert stats["by_confidence"]["low (1-4)"]["correct"] == 0

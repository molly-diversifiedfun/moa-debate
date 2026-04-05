"""Outcome tracking — close the loop on debate verdicts.

Tracks: debate verdict → user decision → actual outcome.
Computes accuracy stats by template, style, and confidence level.
"""

import json
import re
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config import OUTCOMES_FILE, MOA_HOME


def _ensure_file():
    """Ensure the outcomes file and parent directory exist."""
    MOA_HOME.mkdir(exist_ok=True)
    if not OUTCOMES_FILE.exists():
        OUTCOMES_FILE.touch()


_id_counter = 0


def _generate_id() -> str:
    """Generate a unique debate outcome ID from timestamp + counter."""
    global _id_counter
    _id_counter += 1
    return f"debate-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{_id_counter:03d}"


def extract_confidence(verdict: str) -> Optional[int]:
    """Extract confidence score (X/10) from a verdict string.

    Looks for patterns like "Confidence: 7/10" or "## Confidence: 8/10".
    Returns integer 1-10, or None if not found.
    """
    patterns = [
        r'[Cc]onfidence:\s*(\d{1,2})\s*/\s*10',
        r'[Cc]onfidence:\s*\[(\d{1,2})/10\]',
        r'(\d{1,2})\s*/\s*10\s*confidence',
    ]
    for pattern in patterns:
        match = re.search(pattern, verdict)
        if match:
            val = int(match.group(1))
            if 1 <= val <= 10:
                return val
    return None


def log_debate(result: Dict[str, Any]) -> str:
    """Log a debate verdict for future outcome tracking.

    Called automatically after each adversarial debate.
    Returns the outcome ID.
    """
    _ensure_file()
    outcome_id = _generate_id()
    verdict = result.get("response", "")

    entry = {
        "id": outcome_id,
        "ts": datetime.datetime.now().isoformat(),
        "query": result.get("query", ""),
        "verdict": verdict[:500],
        "confidence": extract_confidence(verdict),
        "template": result.get("template"),
        "debate_style": result.get("debate_style", "peer"),
        "angel_model": result.get("angel_model"),
        "devil_model": result.get("devil_model"),
        "converged_at": result.get("converged_at"),
        "research_grounded": result.get("research_grounded", False),
        "decision": None,
        "outcome": None,
        "outcome_ts": None,
        "result_tag": None,  # "good", "bad", "mixed", "unknown"
    }

    with open(OUTCOMES_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return outcome_id


def _read_all() -> List[Dict]:
    """Read all outcome entries."""
    _ensure_file()
    entries = []
    try:
        for line in OUTCOMES_FILE.read_text().strip().split("\n"):
            if line.strip():
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return entries


def _write_all(entries: List[Dict]):
    """Rewrite all outcome entries (for updates)."""
    _ensure_file()
    with open(OUTCOMES_FILE, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def log_decision(outcome_id: str, decision: str) -> bool:
    """Record what the user actually decided after a debate.

    Returns True if the outcome was found and updated.
    """
    entries = _read_all()
    for entry in entries:
        if entry["id"] == outcome_id:
            entry["decision"] = decision
            _write_all(entries)
            return True
    return False


def tag_outcome(outcome_id: str, outcome: str, result_tag: str = "unknown") -> bool:
    """Record what actually happened after the decision.

    result_tag: "good", "bad", "mixed", or "unknown"
    Returns True if the outcome was found and updated.
    """
    valid_tags = ("good", "bad", "mixed", "unknown")
    if result_tag not in valid_tags:
        result_tag = "unknown"

    entries = _read_all()
    for entry in entries:
        if entry["id"] == outcome_id:
            entry["outcome"] = outcome
            entry["outcome_ts"] = datetime.datetime.now().isoformat()
            entry["result_tag"] = result_tag
            _write_all(entries)
            return True
    return False


def get_outcomes(
    pending_only: bool = False,
    stale_days: int = 30,
    stale_only: bool = False,
) -> List[Dict]:
    """Get outcome entries with optional filtering."""
    entries = _read_all()

    if pending_only:
        entries = [e for e in entries if not e.get("outcome")]

    if stale_only:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=stale_days)
        entries = [
            e for e in entries
            if not e.get("outcome")
            and datetime.datetime.fromisoformat(e["ts"]) < cutoff
        ]

    return entries


def compute_stats(entries: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Compute accuracy statistics from outcome entries.

    Returns stats by template, style, and confidence bracket.
    """
    if entries is None:
        entries = _read_all()

    total = len(entries)
    with_outcomes = [e for e in entries if e.get("result_tag") in ("good", "bad", "mixed")]
    pending = [e for e in entries if not e.get("outcome")]

    def _accuracy(subset: List[Dict]) -> Dict:
        if not subset:
            return {"total": 0, "correct": 0, "rate": 0.0}
        correct = sum(1 for e in subset if e.get("result_tag") == "good")
        return {
            "total": len(subset),
            "correct": correct,
            "rate": correct / len(subset) if subset else 0.0,
        }

    # By template
    by_template = {}
    for e in with_outcomes:
        t = e.get("template") or "none"
        by_template.setdefault(t, []).append(e)

    # By style
    by_style = {}
    for e in with_outcomes:
        s = e.get("debate_style", "peer")
        by_style.setdefault(s, []).append(e)

    # By confidence bracket
    by_confidence = {"high (8-10)": [], "medium (5-7)": [], "low (1-4)": []}
    for e in with_outcomes:
        c = e.get("confidence")
        if c is None:
            continue
        if c >= 8:
            by_confidence["high (8-10)"].append(e)
        elif c >= 5:
            by_confidence["medium (5-7)"].append(e)
        else:
            by_confidence["low (1-4)"].append(e)

    # Avg confidence for entries with outcomes
    confidences = [e["confidence"] for e in with_outcomes if e.get("confidence")]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "total_debates": total,
        "with_outcomes": len(with_outcomes),
        "pending": len(pending),
        "overall": _accuracy(with_outcomes),
        "by_template": {k: _accuracy(v) for k, v in by_template.items()},
        "by_style": {k: _accuracy(v) for k, v in by_style.items()},
        "by_confidence": {k: _accuracy(v) for k, v in by_confidence.items()},
        "avg_confidence": round(avg_confidence, 1),
    }

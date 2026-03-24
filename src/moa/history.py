"""JSONL query history logging and spend tracking."""

import json
from datetime import datetime, date
from typing import Optional

from .config import HISTORY_FILE, ensure_moa_home


def log_query(
    query: str,
    tier: str,
    cost_usd: float,
    models_used: list,
    escalated: bool,
    latency_ms: int,
    response_preview: str = "",
):
    """Append a query to the history log."""
    ensure_moa_home()
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "query": query[:200],
        "tier": tier,
        "cost_usd": round(cost_usd, 6),
        "models": models_used,
        "escalated": escalated,
        "latency_ms": latency_ms,
        "response_preview": response_preview[:500],
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_history(n: int = 20) -> list:
    """Get the last N history entries."""
    if not HISTORY_FILE.exists():
        return []

    entries = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return entries[-n:]


def get_history_stats() -> dict:
    """Get aggregate stats from query history."""
    entries = get_history(n=10000)
    if not entries:
        return {
            "total_queries": 0,
            "total_cost": 0.0,
            "avg_latency_ms": 0,
            "escalation_rate": 0.0,
            "queries_today": 0,
            "cost_today": 0.0,
        }

    today = date.today().isoformat()
    today_entries = [e for e in entries if e.get("ts", "").startswith(today)]

    total_cost = sum(e.get("cost_usd", 0) for e in entries)
    escalated = sum(1 for e in entries if e.get("escalated", False))
    avg_latency = sum(e.get("latency_ms", 0) for e in entries) / len(entries)

    return {
        "total_queries": len(entries),
        "total_cost": round(total_cost, 4),
        "avg_latency_ms": int(avg_latency),
        "escalation_rate": round(escalated / len(entries) * 100, 1),
        "queries_today": len(today_entries),
        "cost_today": round(sum(e.get("cost_usd", 0) for e in today_entries), 4),
    }

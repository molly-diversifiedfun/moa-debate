"""Budget tracking and daily cost cap enforcement."""

import json
from datetime import date
from pathlib import Path

from .config import MOA_HOME, USAGE_FILE, MAX_DAILY_SPEND_USD, ensure_moa_home


def _load_usage() -> dict:
    """Load usage data from ~/.moa/usage.json."""
    if not USAGE_FILE.exists():
        return {}
    try:
        return json.loads(USAGE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_usage(usage: dict):
    """Save usage data to ~/.moa/usage.json."""
    ensure_moa_home()
    USAGE_FILE.write_text(json.dumps(usage, indent=2))


def get_today_spend() -> float:
    """Get total spend for today in USD."""
    usage = _load_usage()
    today = date.today().isoformat()
    return usage.get(today, 0.0)


def check_budget(additional_cost: float = 0.0) -> tuple:
    """Check if we're within the daily budget.
    
    Returns (allowed: bool, spend_today: float, cap: float).
    If MAX_DAILY_SPEND_USD is 0, budget is unlimited.
    """
    if MAX_DAILY_SPEND_USD <= 0:
        return True, get_today_spend(), 0.0

    spend = get_today_spend()
    allowed = (spend + additional_cost) <= MAX_DAILY_SPEND_USD
    return allowed, spend, MAX_DAILY_SPEND_USD


def record_spend(cost_usd: float):
    """Record spend for today. Called after each query completion."""
    if cost_usd <= 0:
        return

    ensure_moa_home()
    usage = _load_usage()
    today = date.today().isoformat()
    usage[today] = usage.get(today, 0.0) + cost_usd

    # Prune entries older than 30 days to prevent unbounded growth
    cutoff = date.today().toordinal() - 30
    pruned = {
        k: v for k, v in usage.items()
        if _safe_date_ordinal(k) > cutoff
    }
    _save_usage(pruned)


def get_spend_summary() -> dict:
    """Get spending summary: today, 7-day, 30-day."""
    usage = _load_usage()
    today = date.today()

    day_spend = usage.get(today.isoformat(), 0.0)
    week_spend = sum(
        v for k, v in usage.items()
        if _safe_date_ordinal(k) >= today.toordinal() - 7
    )
    month_spend = sum(usage.values())

    return {
        "today": round(day_spend, 4),
        "week": round(week_spend, 4),
        "month": round(month_spend, 4),
        "cap": MAX_DAILY_SPEND_USD,
        "remaining_today": round(max(0, MAX_DAILY_SPEND_USD - day_spend), 4),
    }


def _safe_date_ordinal(date_str: str) -> int:
    """Parse date string to ordinal, return 0 on failure."""
    try:
        return date.fromisoformat(date_str).toordinal()
    except (ValueError, TypeError):
        return 0

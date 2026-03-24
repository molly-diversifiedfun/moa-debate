"""SQLite-backed response cache with TTL."""

import hashlib
import json
import sqlite3
import time
from typing import Optional

from .config import CACHE_DIR, CACHE_TTL_HOURS, ensure_moa_home


_DB_PATH = CACHE_DIR / "cache.db"
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    """Get or create the SQLite connection."""
    global _conn
    if _conn is None:
        ensure_moa_home()
        _conn = sqlite3.connect(str(_DB_PATH))
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                response TEXT NOT NULL,
                tier TEXT NOT NULL,
                cost_usd REAL DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)
        _conn.commit()
    return _conn


def cache_key(query: str, tier: str) -> str:
    """Generate a deterministic cache key from query + tier."""
    return hashlib.sha256(f"{query.strip().lower()}:{tier}".encode()).hexdigest()[:32]


def get_cached(query: str, tier: str, max_age_hours: Optional[int] = None) -> Optional[dict]:
    """Get a cached response if it exists and is fresh.

    Returns the cached result dict or None.
    """
    ttl = max_age_hours if max_age_hours is not None else CACHE_TTL_HOURS
    key = cache_key(query, tier)
    conn = _get_conn()

    row = conn.execute(
        "SELECT response, cost_usd, created_at FROM cache WHERE key = ?",
        (key,)
    ).fetchone()

    if not row:
        return None

    response_json, cost_usd, created_at = row
    age_hours = (time.time() - created_at) / 3600

    if age_hours > ttl:
        # Expired — delete and return None
        conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        conn.commit()
        return None

    try:
        result = json.loads(response_json)
        result["_cached"] = True
        result["_cache_age_mins"] = round(age_hours * 60, 1)
        return result
    except json.JSONDecodeError:
        return None


def set_cached(query: str, tier: str, result: dict):
    """Store a response in the cache."""
    key = cache_key(query, tier)
    conn = _get_conn()

    # Serialize — strip non-serializable QueryCost object
    cache_result = {k: v for k, v in result.items() if k != "cost"}
    cost_usd = 0.0
    if "cost" in result and hasattr(result["cost"], "estimated_cost_usd"):
        cost_usd = result["cost"].estimated_cost_usd
        cache_result["cost_summary"] = result["cost"].summary()

    conn.execute(
        "INSERT OR REPLACE INTO cache (key, response, tier, cost_usd, created_at) VALUES (?, ?, ?, ?, ?)",
        (key, json.dumps(cache_result), tier, cost_usd, time.time())
    )
    conn.commit()


def clear_cache():
    """Clear all cached responses."""
    conn = _get_conn()
    conn.execute("DELETE FROM cache")
    conn.commit()


def cache_stats() -> dict:
    """Get cache statistics."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    fresh = conn.execute(
        "SELECT COUNT(*) FROM cache WHERE created_at > ?",
        (time.time() - CACHE_TTL_HOURS * 3600,)
    ).fetchone()[0]
    return {"total_entries": total, "fresh_entries": fresh, "stale_entries": total - fresh}

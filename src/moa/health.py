"""Model health tracking with circuit breaker pattern.

Tracks failures per model and fast-fails on models that are consistently down,
instead of wasting 45s × 3 retries before falling back.

States:
- CLOSED (healthy): requests flow normally
- OPEN (broken): requests skip this model immediately
- HALF_OPEN (testing): one request allowed through to test recovery
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import MOA_HOME


HEALTH_FILE = MOA_HOME / "health.json"

# Circuit breaker thresholds
FAILURE_THRESHOLD = 3          # consecutive failures to open circuit
RECOVERY_WINDOW_S = 600       # 10 min before trying a half-open request
HEALTH_DECAY_S = 3600          # 1 hour — old failures stop counting


@dataclass
class ModelHealth:
    consecutive_failures: int = 0
    last_failure_ts: float = 0.0
    last_success_ts: float = 0.0
    total_failures_1h: int = 0
    total_successes_1h: int = 0

    @property
    def is_open(self) -> bool:
        """Circuit is OPEN (broken) — skip this model."""
        if self.consecutive_failures < FAILURE_THRESHOLD:
            return False
        # Check if enough time has passed for half-open
        elapsed = time.time() - self.last_failure_ts
        if elapsed > RECOVERY_WINDOW_S:
            return False  # allow half-open attempt
        return True

    @property
    def is_half_open(self) -> bool:
        """Circuit is HALF_OPEN — allow one test request."""
        if self.consecutive_failures < FAILURE_THRESHOLD:
            return False
        elapsed = time.time() - self.last_failure_ts
        return elapsed > RECOVERY_WINDOW_S

    @property
    def state(self) -> str:
        if self.consecutive_failures < FAILURE_THRESHOLD:
            return "closed"
        elapsed = time.time() - self.last_failure_ts
        if elapsed > RECOVERY_WINDOW_S:
            return "half_open"
        return "open"

    @property
    def success_rate(self) -> float:
        total = self.total_failures_1h + self.total_successes_1h
        if total == 0:
            return 1.0
        return self.total_successes_1h / total


# In-memory cache of model health (loaded from disk on first access)
_health_cache: dict[str, ModelHealth] = {}
_loaded = False


def _load() -> None:
    """Load health data from disk."""
    global _health_cache, _loaded
    _loaded = True
    if not HEALTH_FILE.exists():
        return
    try:
        data = json.loads(HEALTH_FILE.read_text())
        now = time.time()
        for model_name, entry in data.items():
            # Decay old data
            last_failure = entry.get("last_failure_ts", 0)
            if now - last_failure > HEALTH_DECAY_S:
                continue  # stale, skip
            _health_cache[model_name] = ModelHealth(
                consecutive_failures=entry.get("consecutive_failures", 0),
                last_failure_ts=entry.get("last_failure_ts", 0),
                last_success_ts=entry.get("last_success_ts", 0),
                total_failures_1h=entry.get("total_failures_1h", 0),
                total_successes_1h=entry.get("total_successes_1h", 0),
            )
    except (json.JSONDecodeError, KeyError):
        _health_cache = {}


def _save() -> None:
    """Persist health data to disk."""
    MOA_HOME.mkdir(exist_ok=True)
    data = {}
    for model_name, h in _health_cache.items():
        data[model_name] = {
            "consecutive_failures": h.consecutive_failures,
            "last_failure_ts": h.last_failure_ts,
            "last_success_ts": h.last_success_ts,
            "total_failures_1h": h.total_failures_1h,
            "total_successes_1h": h.total_successes_1h,
        }
    HEALTH_FILE.write_text(json.dumps(data, indent=2))


def get_health(model_name: str) -> ModelHealth:
    """Get health status for a model."""
    if not _loaded:
        _load()
    return _health_cache.get(model_name, ModelHealth())


def should_skip(model_name: str) -> Optional[str]:
    """Check if a model should be skipped. Returns reason string or None."""
    health = get_health(model_name)
    if health.is_open:
        elapsed = int(time.time() - health.last_failure_ts)
        return (
            f"circuit open — {health.consecutive_failures} consecutive failures, "
            f"last {elapsed}s ago (retrying in {RECOVERY_WINDOW_S - elapsed}s)"
        )
    return None


def record_success(model_name: str) -> None:
    """Record a successful model call. Resets circuit breaker."""
    if not _loaded:
        _load()
    health = _health_cache.get(model_name, ModelHealth())
    health.consecutive_failures = 0
    health.last_success_ts = time.time()
    health.total_successes_1h += 1
    _health_cache[model_name] = health
    _save()


def record_failure(model_name: str) -> None:
    """Record a failed model call. May open circuit breaker."""
    if not _loaded:
        _load()
    health = _health_cache.get(model_name, ModelHealth())
    health.consecutive_failures += 1
    health.last_failure_ts = time.time()
    health.total_failures_1h += 1
    _health_cache[model_name] = health
    _save()


def get_timeout_for_attempt(base_timeout: int, attempt: int) -> int:
    """Decreasing timeouts per retry: full → half → quarter."""
    if attempt == 0:
        return base_timeout
    elif attempt == 1:
        return max(base_timeout // 2, 10)
    else:
        return max(base_timeout // 4, 5)

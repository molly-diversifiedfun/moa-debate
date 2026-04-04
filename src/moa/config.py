"""Global configuration for the MoA system."""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
MOA_HOME = Path.home() / ".moa"
GLOBAL_ENV = MOA_HOME / ".env"
USAGE_FILE = MOA_HOME / "usage.json"
HISTORY_FILE = MOA_HOME / "history.jsonl"
CACHE_DIR = MOA_HOME / "cache"

# ── Timeouts ───────────────────────────────────────────────────────────────────
MODEL_TIMEOUT_SECONDS = 45          # Per-model call timeout
AGGREGATOR_TIMEOUT_SECONDS = 60     # Aggregators get more time (larger input)

# ── Budget ─────────────────────────────────────────────────────────────────────
MAX_DAILY_SPEND_USD = 5.00          # Daily cost cap (0 = unlimited)

# ── Rate Limiting ──────────────────────────────────────────────────────────────
PROVIDER_CONCURRENCY = {
    "Anthropic": 5,
    "OpenAI": 10,
    "Google": 10,
    "DeepSeek": 3,
    "xAI": 5,
    "Together/Meta": 5,
}

# ── Code Review ────────────────────────────────────────────────────────────────
MAX_DIFF_LINES = 500                # Warn/truncate diffs larger than this
MAX_DIFF_CHARS = 50_000             # Hard limit on diff size sent to models

# ── Cache ──────────────────────────────────────────────────────────────────────
CACHE_TTL_HOURS = 1                 # Response cache time-to-live

# ── Research ──────────────────────────────────────────────────────────────────
RESEARCH_CONTEXT_MAX_CHARS_LITE = 4096   # Max chars for lite search context
RESEARCH_CONTEXT_MAX_CHARS_DEEP = 12288  # Max chars for deep research context

# ── Initialization ─────────────────────────────────────────────────────────────
def ensure_moa_home():
    """Create ~/.moa/ directory structure if it doesn't exist."""
    MOA_HOME.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)

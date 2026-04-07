"""Core engine — backward-compatible re-exports from split modules.

The engine was split in Session 4 (2026-04-05) into:
  orchestrator.py — call_model, cost tracking, agreement, ranking
  adaptive.py     — adaptive routing, MoA, cascade, deep research
  review.py       — expert panel code review
  debate.py       — peer and adversarial debate
"""

# Orchestrator (shared infra)
from .orchestrator import (  # noqa: F401
    call_model,
    calculate_real_cost,
    compute_agreement,
    pairwise_rank,
    _check_budget_or_raise,
    _update_cost,
)

# Adaptive routing, MoA, cascade, deep research, compare
from .adaptive import (  # noqa: F401
    run_adaptive,
    run_moa,
    run_cascade,
    run_deep_research,
    run_compare,
    classify_query,
    get_session_context,
)

# Expert panel code review
from .review import run_expert_review  # noqa: F401

# Debate
from .debate import run_debate, run_peer_pipeline, run_adversarial_pipeline  # noqa: F401
from .debate import PeerDebateState, DebateState, PEER_PIPELINE, ADVERSARIAL_PIPELINE  # noqa: F401

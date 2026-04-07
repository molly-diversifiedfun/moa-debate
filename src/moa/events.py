"""Typed event system for debate progress reporting.

Replaces magic strings like "__FIGHT_START__" with structured events.
CLI and other consumers subscribe to typed events instead of parsing strings.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class EventType(Enum):
    """All event types emitted during a debate."""
    # Animation control
    FIGHT_START = auto()
    FIGHT_STOP = auto()
    JUDGE_START = auto()
    JUDGE_STOP = auto()

    # Debate phases
    TEMPLATE_RESOLVED = auto()
    MODELS_SELECTED = auto()
    RESEARCH_START = auto()
    RESEARCH_COMPLETE = auto()
    OPENING_COMPLETE = auto()
    ROUND_START = auto()
    ROUND_COMPLETE = auto()
    CONVERGENCE_CHECK = auto()
    DEBATE_EXTENDED = auto()
    DEBATE_CONVERGED = auto()
    DEBATE_HARDENED = auto()
    DEBATE_MAX_ROUNDS = auto()
    JUDGE_ENTER = auto()
    JUDGE_COMPLETE = auto()

    # Peer debate phases
    PEER_INDEPENDENT = auto()
    PEER_CHALLENGE = auto()
    PEER_REVISION = auto()
    PEER_JUDGE = auto()

    # Display
    BATTLE_CARD = auto()
    ARGUMENT_PREVIEW = auto()
    AGREEMENT_BAR = auto()

    # Generic text (fallback for unstructured messages)
    MESSAGE = auto()


@dataclass(frozen=True)
class DebateEvent:
    """A single typed event emitted during a debate.

    Attributes:
        type: The event type from EventType enum.
        message: Human-readable text for display.
        data: Optional structured data associated with this event.
        style: Display hint for the CLI (e.g., "bold cyan", "dim").
    """
    type: EventType
    message: str = ""
    data: Optional[dict] = field(default=None, repr=False)
    style: str = ""


# ── Convenience constructors ──────────────────────────────────────────────────

def fight_start() -> DebateEvent:
    return DebateEvent(type=EventType.FIGHT_START)


def fight_stop() -> DebateEvent:
    return DebateEvent(type=EventType.FIGHT_STOP)


def judge_start() -> DebateEvent:
    return DebateEvent(type=EventType.JUDGE_START)


def judge_stop() -> DebateEvent:
    return DebateEvent(type=EventType.JUDGE_STOP)


def battle_card(text: str) -> DebateEvent:
    return DebateEvent(type=EventType.BATTLE_CARD, message=text, style="bold cyan")


def template_resolved(name: str, description: str, auto_detected: bool = False) -> DebateEvent:
    icon = "💡" if auto_detected else "📋"
    verb = "Auto-detected" if auto_detected else "Using"
    return DebateEvent(
        type=EventType.TEMPLATE_RESOLVED,
        message=f"{icon} {verb} '{name}' template: {description}",
        data={"name": name, "auto_detected": auto_detected},
        style="bold magenta",
    )


def template_unknown(name: str) -> DebateEvent:
    return DebateEvent(
        type=EventType.MESSAGE,
        message=f"⚠️  Unknown template '{name}' — running without template",
        style="yellow",
    )


def models_selected(angel: str, devil: str, skipped: list = None) -> DebateEvent:
    return DebateEvent(
        type=EventType.MODELS_SELECTED,
        message="",
        data={"angel": angel, "devil": devil, "skipped": skipped or []},
    )


def skipped_unhealthy(names: list) -> DebateEvent:
    return DebateEvent(
        type=EventType.MESSAGE,
        message=f"⚡ Skipping unhealthy models: {', '.join(names)}",
        style="yellow",
    )


def research_start(provider_names: list) -> DebateEvent:
    return DebateEvent(
        type=EventType.RESEARCH_START,
        message=f"🔍 Researching both sides ({' → '.join(provider_names)})...",
        data={"providers": provider_names},
        style="bold blue",
    )


def research_complete(source_count: int) -> DebateEvent:
    if source_count > 0:
        msg = f"📚 Found {source_count} sources — both sides will cite real evidence"
    else:
        msg = "📚 No research results — debating from training data"
    return DebateEvent(
        type=EventType.RESEARCH_COMPLETE,
        message=msg,
        data={"source_count": source_count},
        style="bold blue",
    )


def research_unavailable() -> DebateEvent:
    return DebateEvent(
        type=EventType.RESEARCH_COMPLETE,
        message="📚 No research providers — debating from training data",
        data={"source_count": 0},
        style="bold blue",
    )


def argument_preview(role: str, thesis: str, word_count: int) -> DebateEvent:
    icon = "👼" if role == "angel" else "😈"
    label = "ADVOCATE" if role == "angel" else "CRITIC"
    return DebateEvent(
        type=EventType.ARGUMENT_PREVIEW,
        message=f"\n   {icon} {label} opens:\n   │ \"{thesis}\"\n   │ ({word_count} words)",
        data={"role": role, "thesis": thesis, "word_count": word_count},
    )


def round_start(round_num: int, message: str) -> DebateEvent:
    return DebateEvent(
        type=EventType.ROUND_START,
        message=f"\n{message}",
        style="bold cyan",
    )


def round_thesis(role: str, thesis: str) -> DebateEvent:
    icon = "👼" if role == "angel" else "😈"
    return DebateEvent(
        type=EventType.MESSAGE,
        message=f"   {icon} \"{thesis}\"",
        style="bold white",
    )


def agreement_bar(score: float) -> DebateEvent:
    filled = int(score * 20)
    bar = "█" * filled + "░" * (20 - filled)
    return DebateEvent(
        type=EventType.AGREEMENT_BAR,
        message=f"   [{bar}] {score:.0%} agreement",
        data={"score": score},
        style="yellow",
    )


def opening_agreement(score: float) -> DebateEvent:
    return DebateEvent(
        type=EventType.CONVERGENCE_CHECK,
        message=f"\n   📊 Opening agreement: {score:.0%}",
        data={"score": score},
        style="cyan",
    )


def converged(round_num: int) -> DebateEvent:
    return DebateEvent(
        type=EventType.DEBATE_CONVERGED,
        message="   🤝 They're... agreeing? Debate over.",
        data={"round": round_num},
        style="bold green",
    )


def hardened(delta: float) -> DebateEvent:
    return DebateEvent(
        type=EventType.DEBATE_HARDENED,
        message=f"   🪨 Positions hardened (Δ{delta:.0%}). Neither will budge.",
        data={"delta": delta},
        style="yellow",
    )


def extended(delta: float) -> DebateEvent:
    return DebateEvent(
        type=EventType.DEBATE_EXTENDED,
        message=f"   🔄 Still shifting (Δ{delta:.0%}) — extending debate...",
        data={"delta": delta},
        style="magenta",
    )


def max_rounds() -> DebateEvent:
    return DebateEvent(
        type=EventType.DEBATE_MAX_ROUNDS,
        message="   ⏰ Max rounds reached.",
        style="yellow",
    )


def judge_enter(total_rounds: int) -> DebateEvent:
    return DebateEvent(
        type=EventType.JUDGE_ENTER,
        message=f"{'─' * 40}\n⚖️  JUDGE ENTERS ({total_rounds} rounds of testimony)\n{'─' * 40}",
        data={"total_rounds": total_rounds},
        style="bold yellow",
    )


# ── Peer debate events ──────────────────────────────────────────────────────

def peer_independent(model_count: int, model_names: list) -> DebateEvent:
    return DebateEvent(
        type=EventType.PEER_INDEPENDENT,
        message=f"📝 {model_count} models forming independent opinions... ({', '.join(model_names)})",
        data={"model_count": model_count, "model_names": model_names},
        style="bold cyan",
    )


def peer_challenge() -> DebateEvent:
    return DebateEvent(
        type=EventType.PEER_CHALLENGE,
        message='🔍 Challenge round: "Find something wrong. No, really. We insist."',
        style="bold yellow",
    )


def peer_revision(round_num: int, message: str) -> DebateEvent:
    return DebateEvent(
        type=EventType.PEER_REVISION,
        message=f"\n{message}",
        data={"round": round_num},
        style="bold cyan",
    )


def peer_agreement(score: float) -> DebateEvent:
    filled = int(score * 20)
    bar = "█" * filled + "░" * (20 - filled)
    return DebateEvent(
        type=EventType.AGREEMENT_BAR,
        message=f"   [{bar}] {score:.0%} agreement",
        data={"score": score},
        style="yellow",
    )


def peer_converged(round_num: int, score: float) -> DebateEvent:
    return DebateEvent(
        type=EventType.DEBATE_CONVERGED,
        message=f"🤝 Consensus reached at round {round_num}! Agreement: {score:.0%}. They actually agree now.",
        data={"round": round_num, "score": score},
        style="bold green",
    )


def peer_no_consensus(score: float) -> DebateEvent:
    return DebateEvent(
        type=EventType.DEBATE_HARDENED,
        message=f"   📊 Agreement: {score:.0%} — still fighting.",
        data={"score": score},
        style="yellow",
    )


def peer_judge() -> DebateEvent:
    return DebateEvent(
        type=EventType.PEER_JUDGE,
        message="⚖️  Judge enters the room. Reviewing all arguments...",
        style="bold yellow",
    )

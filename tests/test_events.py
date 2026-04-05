"""Tests for the typed debate event system."""

from moa.events import (
    EventType, DebateEvent,
    fight_start, fight_stop, judge_start, judge_stop,
    battle_card, template_resolved, template_unknown,
    models_selected, skipped_unhealthy,
    research_start, research_complete, research_unavailable,
    argument_preview, round_start, round_thesis,
    agreement_bar, opening_agreement,
    converged, hardened, extended, max_rounds,
    judge_enter,
)


# ── EventType enum ────────────────────────────────────────────────────────────

def test_event_type_has_all_phases():
    """EventType should cover all debate phases."""
    assert EventType.FIGHT_START
    assert EventType.FIGHT_STOP
    assert EventType.JUDGE_START
    assert EventType.JUDGE_STOP
    assert EventType.TEMPLATE_RESOLVED
    assert EventType.MODELS_SELECTED
    assert EventType.RESEARCH_START
    assert EventType.RESEARCH_COMPLETE
    assert EventType.OPENING_COMPLETE
    assert EventType.ROUND_START
    assert EventType.ROUND_COMPLETE
    assert EventType.CONVERGENCE_CHECK
    assert EventType.DEBATE_CONVERGED
    assert EventType.DEBATE_HARDENED
    assert EventType.DEBATE_EXTENDED
    assert EventType.DEBATE_MAX_ROUNDS
    assert EventType.JUDGE_ENTER
    assert EventType.BATTLE_CARD
    assert EventType.ARGUMENT_PREVIEW
    assert EventType.AGREEMENT_BAR
    assert EventType.MESSAGE


# ── DebateEvent dataclass ─────────────────────────────────────────────────────

def test_debate_event_is_frozen():
    """DebateEvent should be immutable (frozen dataclass)."""
    event = DebateEvent(type=EventType.FIGHT_START)
    try:
        event.type = EventType.FIGHT_STOP
        assert False, "Should not be able to mutate frozen dataclass"
    except AttributeError:
        pass


def test_debate_event_defaults():
    """DebateEvent should have sensible defaults."""
    event = DebateEvent(type=EventType.MESSAGE)
    assert event.message == ""
    assert event.data is None
    assert event.style == ""


# ── Animation control events ─────────────────────────────────────────────────

def test_fight_start():
    event = fight_start()
    assert event.type == EventType.FIGHT_START
    assert event.message == ""


def test_fight_stop():
    event = fight_stop()
    assert event.type == EventType.FIGHT_STOP


def test_judge_start():
    event = judge_start()
    assert event.type == EventType.JUDGE_START


def test_judge_stop():
    event = judge_stop()
    assert event.type == EventType.JUDGE_STOP


# ── Template events ──────────────────────────────────────────────────────────

def test_template_resolved_explicit():
    event = template_resolved("hire", "Hiring decisions")
    assert event.type == EventType.TEMPLATE_RESOLVED
    assert "hire" in event.message
    assert "📋" in event.message
    assert event.data["name"] == "hire"
    assert event.data["auto_detected"] is False


def test_template_resolved_autodetected():
    event = template_resolved("build", "Build vs buy", auto_detected=True)
    assert "💡" in event.message
    assert event.data["auto_detected"] is True


def test_template_unknown():
    event = template_unknown("nonexistent")
    assert event.type == EventType.MESSAGE
    assert "Unknown template" in event.message


# ── Model selection events ───────────────────────────────────────────────────

def test_models_selected():
    event = models_selected("claude-opus", "gpt-5")
    assert event.type == EventType.MODELS_SELECTED
    assert event.data["angel"] == "claude-opus"
    assert event.data["devil"] == "gpt-5"


def test_skipped_unhealthy():
    event = skipped_unhealthy(["gemini-pro", "grok-4"])
    assert "gemini-pro" in event.message
    assert "grok-4" in event.message


# ── Research events ──────────────────────────────────────────────────────────

def test_research_start():
    event = research_start(["Firecrawl", "DuckDuckGo"])
    assert event.type == EventType.RESEARCH_START
    assert "Firecrawl" in event.message
    assert event.data["providers"] == ["Firecrawl", "DuckDuckGo"]


def test_research_complete_with_sources():
    event = research_complete(5)
    assert "5 sources" in event.message
    assert event.data["source_count"] == 5


def test_research_complete_no_sources():
    event = research_complete(0)
    assert "No research results" in event.message


def test_research_unavailable():
    event = research_unavailable()
    assert "No research providers" in event.message


# ── Argument preview events ──────────────────────────────────────────────────

def test_argument_preview_angel():
    event = argument_preview("angel", "73% of companies improved", 250)
    assert event.type == EventType.ARGUMENT_PREVIEW
    assert "ADVOCATE" in event.message
    assert "👼" in event.message
    assert event.data["role"] == "angel"
    assert event.data["word_count"] == 250


def test_argument_preview_devil():
    event = argument_preview("devil", "Failure rates exceed 50%", 180)
    assert "CRITIC" in event.message
    assert "😈" in event.message


# ── Round events ─────────────────────────────────────────────────────────────

def test_round_start():
    event = round_start(2, "⚔️  Round 2: Gloves off.")
    assert event.type == EventType.ROUND_START
    assert "Round 2" in event.message


def test_round_thesis():
    event = round_thesis("angel", "The data clearly shows...")
    assert "👼" in event.message
    assert "data clearly shows" in event.message


# ── Agreement events ─────────────────────────────────────────────────────────

def test_agreement_bar():
    event = agreement_bar(0.45)
    assert event.type == EventType.AGREEMENT_BAR
    assert "█" in event.message
    assert "45%" in event.message
    assert event.data["score"] == 0.45


def test_opening_agreement():
    event = opening_agreement(0.32)
    assert event.type == EventType.CONVERGENCE_CHECK
    assert "32%" in event.message


# ── Convergence events ───────────────────────────────────────────────────────

def test_converged():
    event = converged(3)
    assert event.type == EventType.DEBATE_CONVERGED
    assert "🤝" in event.message
    assert event.data["round"] == 3


def test_hardened():
    event = hardened(0.02)
    assert event.type == EventType.DEBATE_HARDENED
    assert "🪨" in event.message


def test_extended():
    event = extended(0.05)
    assert event.type == EventType.DEBATE_EXTENDED
    assert "🔄" in event.message


def test_max_rounds():
    event = max_rounds()
    assert event.type == EventType.DEBATE_MAX_ROUNDS
    assert "⏰" in event.message


# ── Judge events ─────────────────────────────────────────────────────────────

def test_judge_enter():
    event = judge_enter(3)
    assert event.type == EventType.JUDGE_ENTER
    assert "3 rounds" in event.message
    assert event.data["total_rounds"] == 3

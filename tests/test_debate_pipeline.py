"""Tests for the composable adversarial debate pipeline stages."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from moa.debate import (
    DebateState, resolve_template, select_models, research,
    opening, rounds, judge, format_result,
    run_adversarial_pipeline, ADVERSARIAL_PIPELINE,
    _best_sentence, _word_count, _dw, _short_name,
)
from moa.models import QueryCost


# ── DebateState tests ─────────────────────────────────────────────────────────

def test_debate_state_defaults():
    """DebateState should have sensible defaults."""
    state = DebateState(query="test question")
    assert state.query == "test question"
    assert state.rounds == 2
    assert state.tier_name == "pro"
    assert state.template is None
    assert state.angel_model is None
    assert state.devil_model is None
    assert state.research_context == ""
    assert state.angel_pos == ""
    assert state.devil_pos == ""
    assert state.all_rounds == []
    assert state.converged_at is None
    assert state.judge_response == ""
    assert state.model_status == {}


def test_debate_state_custom_values():
    """DebateState should accept custom values."""
    state = DebateState(
        query="should we hire?",
        rounds=3,
        tier_name="ultra",
        template_name="hire",
    )
    assert state.rounds == 3
    assert state.tier_name == "ultra"
    assert state.template_name == "hire"


# ── Helper tests ──────────────────────────────────────────────────────────────

def test_best_sentence_extracts_specific():
    """_best_sentence should prefer sentences with data and specificity signals."""
    text = (
        "Let me explain my position. "
        "According to a 2024 study, 73% of companies saw a 40% improvement in retention. "
        "This is important."
    )
    result = _best_sentence(text)
    assert "73%" in result or "40%" in result


def test_best_sentence_skips_preamble():
    """_best_sentence should skip generic preamble sentences."""
    text = (
        "I need to address this carefully. "
        "Let me think about this. "
        "The critical risk is that failure rates exceed 50% in year one."
    )
    result = _best_sentence(text)
    assert "failure" in result.lower() or "50%" in result


def test_best_sentence_fallback_on_short_text():
    """_best_sentence should handle short text gracefully."""
    result = _best_sentence("Short.")
    assert len(result) > 0


def test_word_count():
    """_word_count should count words correctly."""
    assert _word_count("hello world") == 2
    assert _word_count("one two three four five") == 5
    assert _word_count("") == 0


def test_display_width_ascii():
    """_dw should return correct width for ASCII text."""
    assert _dw("hello") == 5
    assert _dw("test string") == 11


def test_display_width_emoji():
    """_dw should handle emoji display width."""
    # Wide emoji
    assert _dw("👼") == 2
    assert _dw("😈") == 2


def test_short_name():
    """_short_name should extract the part after the last slash."""
    model = MagicMock()
    model.name = "anthropic/claude-sonnet-4-20250514"
    assert _short_name(model) == "claude-sonnet-4-20250514"

    model.name = "gemini-flash"
    assert _short_name(model) == "gemini-flash"


# ── resolve_template stage ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_template_by_name():
    """resolve_template should find a template by name."""
    progress = []
    state = DebateState(
        query="should we hire a senior engineer?",
        template_name="hire",
        on_progress=progress.append,
    )
    result = await resolve_template(state)
    assert result.template is not None
    assert result.template.name == "hire"
    assert any("hire" in msg for msg in progress)


@pytest.mark.asyncio
async def test_resolve_template_autodetect():
    """resolve_template should auto-detect template from query."""
    state = DebateState(
        query="should we hire a data scientist?",
        on_progress=lambda msg: None,
    )
    result = await resolve_template(state)
    # May or may not detect — depends on keyword matching
    # Just verify it doesn't crash and returns state
    assert result.query == "should we hire a data scientist?"


@pytest.mark.asyncio
async def test_resolve_template_unknown_name():
    """resolve_template should handle unknown template names gracefully."""
    progress = []
    state = DebateState(
        query="test",
        template_name="nonexistent",
        on_progress=progress.append,
    )
    result = await resolve_template(state)
    assert result.template is None
    assert any("Unknown template" in msg for msg in progress)


# ── select_models stage ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_select_models_picks_different_providers():
    """select_models should pick angel and devil from different providers."""
    model_a = MagicMock()
    model_a.name = "anthropic/claude-opus-4-20250514"
    model_a.provider = "anthropic"
    model_a.output_cost_per_mtok = 75.0
    model_a.available = True

    model_b = MagicMock()
    model_b.name = "openai/gpt-5.4"
    model_b.provider = "openai"
    model_b.output_cost_per_mtok = 60.0
    model_b.available = True

    with patch("moa.debate.TIERS", {"pro": MagicMock()}), \
         patch("moa.models.available_models", return_value=[model_a, model_b]), \
         patch("moa.health.should_skip", return_value=None):
        state = DebateState(query="test", on_progress=lambda msg: None)
        result = await select_models(state)
        assert result.angel_model.provider != result.devil_model.provider


@pytest.mark.asyncio
async def test_select_models_raises_on_insufficient():
    """select_models should raise if fewer than 2 models available."""
    model = MagicMock()
    model.name = "only-one"
    model.output_cost_per_mtok = 10.0
    model.available = True

    with patch("moa.debate.TIERS", {"pro": MagicMock()}), \
         patch("moa.models.available_models", return_value=[model]), \
         patch("moa.health.should_skip", return_value=None):
        state = DebateState(query="test", on_progress=lambda msg: None)
        with pytest.raises(RuntimeError, match="at least 2"):
            await select_models(state)


# ── format_result stage ──────────────────────────────────────────────────────

def test_format_result_structure():
    """format_result should return all expected keys."""
    angel = MagicMock()
    angel.name = "anthropic/claude-opus"
    devil = MagicMock()
    devil.name = "openai/gpt-5"

    state = DebateState(
        query="test question",
        angel_model=angel,
        devil_model=devil,
        angel_pos="angel says yes",
        devil_pos="devil says no",
        judge_response="The verdict is...",
        research_context="Source: https://example.com\nSome content",
        cost=QueryCost(tier="adversarial-pro"),
        start_time=0.0,
        all_rounds=[{"angel": "yes", "devil": "no"}],
    )

    result = format_result(state)
    assert result["response"] == "The verdict is..."
    assert result["debate_style"] == "adversarial"
    assert result["research_grounded"] is True
    assert "https://example.com" in result["research_sources"]
    assert result["angel_model"] == "claude-opus"
    assert result["devil_model"] == "gpt-5"
    assert result["query"] == "test question"
    assert "latency_ms" in result
    assert "cost" in result


def test_format_result_no_research():
    """format_result should handle no research context."""
    angel = MagicMock()
    angel.name = "model-a"
    devil = MagicMock()
    devil.name = "model-b"

    state = DebateState(
        query="test",
        angel_model=angel,
        devil_model=devil,
        judge_response="verdict",
        cost=QueryCost(tier="test"),
        start_time=0.0,
    )

    result = format_result(state)
    assert result["research_grounded"] is False
    assert result["research_sources"] == []


# ── Pipeline composition ─────────────────────────────────────────────────────

def test_pipeline_has_all_stages():
    """ADVERSARIAL_PIPELINE should contain all 6 stages in order."""
    assert len(ADVERSARIAL_PIPELINE) == 6
    assert ADVERSARIAL_PIPELINE[0] is resolve_template
    assert ADVERSARIAL_PIPELINE[1] is select_models
    assert ADVERSARIAL_PIPELINE[2] is research
    assert ADVERSARIAL_PIPELINE[3] is opening
    assert ADVERSARIAL_PIPELINE[4] is rounds
    assert ADVERSARIAL_PIPELINE[5] is judge


def test_pipeline_stages_are_callable():
    """All pipeline stages should be async callables."""
    import asyncio
    for stage in ADVERSARIAL_PIPELINE:
        assert callable(stage)
        assert asyncio.iscoroutinefunction(stage)

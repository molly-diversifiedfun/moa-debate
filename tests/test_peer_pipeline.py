"""Tests for the composable peer debate pipeline stages."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from moa.debate import (
    PeerDebateState, peer_select_models, peer_independent, peer_challenge,
    peer_revision_rounds, peer_judge, peer_format_result,
    run_peer_pipeline, PEER_PIPELINE, run_debate,
)
from moa.models import QueryCost


# ── PeerDebateState tests ────────────────────────────────────────────────────

def test_peer_debate_state_defaults():
    """PeerDebateState should have sensible defaults."""
    state = PeerDebateState(query="test question")
    assert state.query == "test question"
    assert state.rounds == 2
    assert state.tier_name == "pro"
    assert state.available_models == []
    assert state.current_positions == {}
    assert state.challenges_by_model == {}
    assert state.all_rounds == []
    assert state.converged_at is None
    assert state.judge_response == ""
    assert state.model_status == {}


def test_peer_debate_state_custom_values():
    """PeerDebateState should accept custom values."""
    state = PeerDebateState(
        query="should we use Redis?",
        rounds=3,
        tier_name="ultra",
    )
    assert state.rounds == 3
    assert state.tier_name == "ultra"


# ── Pipeline structure ───────────────────────────────────────────────────────

def test_peer_pipeline_has_all_stages():
    """PEER_PIPELINE should contain all 5 stages in order."""
    assert len(PEER_PIPELINE) == 5
    assert PEER_PIPELINE[0] is peer_select_models
    assert PEER_PIPELINE[1] is peer_independent
    assert PEER_PIPELINE[2] is peer_challenge
    assert PEER_PIPELINE[3] is peer_revision_rounds
    assert PEER_PIPELINE[4] is peer_judge


def test_peer_pipeline_stages_are_callable():
    """All peer pipeline stages should be async callables."""
    import asyncio
    for stage in PEER_PIPELINE:
        assert callable(stage)
        assert asyncio.iscoroutinefunction(stage)


# ── peer_select_models stage ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_peer_select_models_populates_available():
    """peer_select_models should populate available_models from tier."""
    model_a = MagicMock()
    model_a.name = "model-a"
    model_a.available = True
    model_b = MagicMock()
    model_b.name = "model-b"
    model_b.available = True

    tier = MagicMock()
    tier.available_proposers = [model_a, model_b]

    with patch("moa.debate.TIERS", {"pro": tier}):
        events = []
        state = PeerDebateState(
            query="test", on_progress=events.append,
            cost=QueryCost(tier="peer-pro"),
        )
        result = await peer_select_models(state)
        assert len(result.available_models) == 2
        assert len(events) == 1  # peer_independent event


@pytest.mark.asyncio
async def test_peer_select_models_raises_on_insufficient():
    """peer_select_models should raise with <2 models."""
    model = MagicMock()
    model.name = "only-one"
    model.available = True

    tier = MagicMock()
    tier.available_proposers = [model]

    with patch("moa.debate.TIERS", {"pro": tier}):
        state = PeerDebateState(query="test", on_progress=lambda m: None)
        with pytest.raises(RuntimeError, match="at least 2"):
            await peer_select_models(state)


@pytest.mark.asyncio
async def test_peer_select_models_raises_on_unknown_tier():
    """peer_select_models should raise on unknown tier."""
    with patch("moa.debate.TIERS", {}):
        state = PeerDebateState(query="test", tier_name="fake", on_progress=lambda m: None)
        with pytest.raises(ValueError, match="Unknown tier"):
            await peer_select_models(state)


# ── peer_independent stage ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_peer_independent_gathers_positions():
    """peer_independent should call all models and collect positions."""
    model_a = MagicMock()
    model_a.name = "provider-a/model-a"
    model_b = MagicMock()
    model_b.name = "provider-b/model-b"

    result_a = {"content": "answer A", "latency_s": 1.0, "input_tokens": 10,
                "output_tokens": 50, "cost_usd": 0.01, "model": "model-a", "provider": "a"}
    result_b = {"content": "answer B", "latency_s": 1.2, "input_tokens": 10,
                "output_tokens": 50, "cost_usd": 0.01, "model": "model-b", "provider": "b"}

    with patch("moa.debate.call_model", new_callable=AsyncMock, side_effect=[result_a, result_b]):
        state = PeerDebateState(
            query="test",
            available_models=[model_a, model_b],
            cost=QueryCost(tier="peer-pro"),
            on_progress=lambda m: None,
        )
        result = await peer_independent(state)
        assert len(result.current_positions) == 2
        assert result.current_positions["provider-a/model-a"] == "answer A"
        assert result.current_positions["provider-b/model-b"] == "answer B"
        assert len(result.all_rounds) == 1


@pytest.mark.asyncio
async def test_peer_independent_handles_failures():
    """peer_independent should handle model failures gracefully."""
    model_a = MagicMock()
    model_a.name = "model-a"
    model_b = MagicMock()
    model_b.name = "model-b"
    model_c = MagicMock()
    model_c.name = "model-c"

    result_a = {"content": "A", "latency_s": 1.0, "input_tokens": 10,
                "output_tokens": 50, "cost_usd": 0.01, "model": "a", "provider": "a"}
    result_c = {"content": "C", "latency_s": 1.0, "input_tokens": 10,
                "output_tokens": 50, "cost_usd": 0.01, "model": "c", "provider": "c"}

    with patch("moa.debate.call_model", new_callable=AsyncMock, side_effect=[result_a, None, result_c]):
        state = PeerDebateState(
            query="test",
            available_models=[model_a, model_b, model_c],
            cost=QueryCost(tier="peer-pro"),
            on_progress=lambda m: None,
        )
        result = await peer_independent(state)
        assert len(result.current_positions) == 2
        assert "model-b" not in result.current_positions
        assert result.model_status["model-b"] == "❌ failed R0"


@pytest.mark.asyncio
async def test_peer_independent_raises_on_all_failures():
    """peer_independent should raise if <2 models respond."""
    model_a = MagicMock()
    model_a.name = "model-a"
    model_b = MagicMock()
    model_b.name = "model-b"

    with patch("moa.debate.call_model", new_callable=AsyncMock, return_value=None):
        state = PeerDebateState(
            query="test",
            available_models=[model_a, model_b],
            cost=QueryCost(tier="peer-pro"),
            on_progress=lambda m: None,
        )
        with pytest.raises(RuntimeError, match="Less than 2"):
            await peer_independent(state)


# ── peer_format_result ───────────────────────────────────────────────────────

def test_peer_format_result_structure():
    """peer_format_result should return expected keys."""
    state = PeerDebateState(
        query="test",
        judge_response="Final verdict",
        all_rounds=[{"a": "x"}, {"a": "y"}],
        model_status={"a": "ok"},
        cost=QueryCost(tier="peer-pro"),
        converged_at=2,
        start_time=0.0,
    )
    result = peer_format_result(state)
    assert result["response"] == "Final verdict"
    assert result["debate_style"] == "peer"
    assert result["converged_at"] == 2
    assert "latency_ms" in result
    assert len(result["rounds"]) == 2


# ── run_debate dispatches correctly ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_debate_peer_uses_pipeline():
    """run_debate with style='peer' should delegate to run_peer_pipeline."""
    with patch("moa.debate.run_peer_pipeline", new_callable=AsyncMock, return_value={"response": "ok"}) as mock:
        result = await run_debate("test query", debate_style="peer")
        mock.assert_called_once()
        assert result["response"] == "ok"


@pytest.mark.asyncio
async def test_run_debate_adversarial_uses_pipeline():
    """run_debate with style='adversarial' should delegate to run_adversarial_pipeline."""
    with patch("moa.debate.run_adversarial_pipeline", new_callable=AsyncMock, return_value={"response": "ok"}) as mock:
        result = await run_debate("test query", debate_style="adversarial")
        mock.assert_called_once()
        assert result["response"] == "ok"

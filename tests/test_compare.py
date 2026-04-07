"""Tests for the compare feature (single model vs ensemble)."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from moa.adaptive import run_compare
from moa.models import ModelConfig, QueryCost


def _make_model(name: str = "anthropic/claude-sonnet", provider: str = "Anthropic") -> ModelConfig:
    """Create a test ModelConfig."""
    return ModelConfig(
        name=name, provider=provider, env_key="TEST_KEY",
        input_cost_per_mtok=3.0, output_cost_per_mtok=15.0,
    )


def _make_call_result(content: str = "response", cost: float = 0.01) -> dict:
    return {
        "content": content, "latency_s": 1.0,
        "input_tokens": 100, "output_tokens": 200,
        "cost_usd": cost, "model": "test", "provider": "test",
    }


def _make_moa_result(response: str = "ensemble response", proposals: list = None) -> dict:
    return {
        "response": response,
        "proposals": proposals or ["p1", "p2"],
        "model_names": ["model-a", "model-b"],
        "model_status": {"a": "ok"},
        "cost": QueryCost(tier="lite"),
        "latency_ms": 2000,
    }


# ── run_compare tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compare_returns_both_responses():
    """run_compare should return both single and ensemble responses."""
    model = _make_model()
    single_r = _make_call_result("single answer")
    moa_r = _make_moa_result("ensemble answer")

    with patch("moa.adaptive._check_budget_or_raise"), \
         patch("moa.adaptive.call_model", new_callable=AsyncMock, return_value=single_r), \
         patch("moa.adaptive.run_moa", new_callable=AsyncMock, return_value=moa_r), \
         patch("moa.adaptive.compute_agreement", return_value={"score": 0.6, "details": ""}), \
         patch("moa.adaptive.pairwise_rank", new_callable=AsyncMock,
               return_value={"best_index": 1, "wins": [0, 1]}), \
         patch("moa.adaptive.record_spend"):
        result = await run_compare("test query", single_model=model)

        assert result["single_response"] == "single answer"
        assert result["ensemble_response"] == "ensemble answer"
        assert "agreement_score" in result
        assert result["agreement_score"] == 0.6


@pytest.mark.asyncio
async def test_compare_identifies_best_source():
    """run_compare should correctly identify which source won ranking."""
    model = _make_model()

    with patch("moa.adaptive._check_budget_or_raise"), \
         patch("moa.adaptive.call_model", new_callable=AsyncMock, return_value=_make_call_result()), \
         patch("moa.adaptive.run_moa", new_callable=AsyncMock, return_value=_make_moa_result()), \
         patch("moa.adaptive.compute_agreement", return_value={"score": 0.5}), \
         patch("moa.adaptive.pairwise_rank", new_callable=AsyncMock,
               return_value={"best_index": 0, "wins": [1, 0]}), \
         patch("moa.adaptive.record_spend"):
        result = await run_compare("test", single_model=model)
        assert result["best_source"] == "single"

    with patch("moa.adaptive._check_budget_or_raise"), \
         patch("moa.adaptive.call_model", new_callable=AsyncMock, return_value=_make_call_result()), \
         patch("moa.adaptive.run_moa", new_callable=AsyncMock, return_value=_make_moa_result()), \
         patch("moa.adaptive.compute_agreement", return_value={"score": 0.5}), \
         patch("moa.adaptive.pairwise_rank", new_callable=AsyncMock,
               return_value={"best_index": 1, "wins": [0, 1]}), \
         patch("moa.adaptive.record_spend"):
        result = await run_compare("test", single_model=model)
        assert result["best_source"] == "ensemble"


@pytest.mark.asyncio
async def test_compare_tracks_costs():
    """run_compare should track cost delta between single and ensemble."""
    model = _make_model()
    single_r = _make_call_result(cost=0.005)
    moa_r = _make_moa_result()

    with patch("moa.adaptive._check_budget_or_raise"), \
         patch("moa.adaptive.call_model", new_callable=AsyncMock, return_value=single_r), \
         patch("moa.adaptive.run_moa", new_callable=AsyncMock, return_value=moa_r), \
         patch("moa.adaptive.compute_agreement", return_value={"score": 0.5}), \
         patch("moa.adaptive.pairwise_rank", new_callable=AsyncMock,
               return_value={"best_index": 0, "wins": [1, 0]}), \
         patch("moa.adaptive.record_spend"):
        result = await run_compare("test", single_model=model)
        assert result["single_cost_usd"] == 0.005
        assert "cost_delta_usd" in result
        assert "latency_ms" in result


@pytest.mark.asyncio
async def test_compare_raises_on_single_failure():
    """run_compare should raise if the single model fails."""
    model = _make_model()

    with patch("moa.adaptive._check_budget_or_raise"), \
         patch("moa.adaptive.call_model", new_callable=AsyncMock, return_value=None), \
         patch("moa.adaptive.run_moa", new_callable=AsyncMock, return_value=_make_moa_result()):
        with pytest.raises(RuntimeError, match="failed to respond"):
            await run_compare("test", single_model=model)


@pytest.mark.asyncio
async def test_compare_includes_ensemble_metadata():
    """run_compare should include ensemble model names and proposals."""
    model = _make_model()
    moa_r = _make_moa_result(proposals=["proposal 1", "proposal 2", "proposal 3"])

    with patch("moa.adaptive._check_budget_or_raise"), \
         patch("moa.adaptive.call_model", new_callable=AsyncMock, return_value=_make_call_result()), \
         patch("moa.adaptive.run_moa", new_callable=AsyncMock, return_value=moa_r), \
         patch("moa.adaptive.compute_agreement", return_value={"score": 0.5}), \
         patch("moa.adaptive.pairwise_rank", new_callable=AsyncMock,
               return_value={"best_index": 0, "wins": [1, 0]}), \
         patch("moa.adaptive.record_spend"):
        result = await run_compare("test", single_model=model)
        assert result["ensemble_tier"] == "lite"
        assert result["ensemble_models"] == ["model-a", "model-b"]
        assert len(result["ensemble_proposals"]) == 3

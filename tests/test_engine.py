"""Tests for the MoA engine."""

import asyncio
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("GEMINI_API_KEY", "test-key")


def test_model_roster_size():
    """Should have 14 models in the roster."""
    from moa.models import ALL_MODELS
    assert len(ALL_MODELS) == 14


def test_all_providers_represented():
    """All 6 providers should be in the roster."""
    from moa.models import ALL_MODELS
    providers = set(m.provider for m in ALL_MODELS)
    assert "Anthropic" in providers
    assert "OpenAI" in providers
    assert "Google" in providers
    assert "DeepSeek" in providers
    assert "xAI" in providers
    assert "Together/Meta" in providers


def test_model_availability():
    """Models with set env keys should report as available."""
    from moa.models import GEMINI_FLASH, GPT4O_MINI
    assert GEMINI_FLASH.available is True
    if os.environ.get("OPENAI_API_KEY"):
        assert GPT4O_MINI.available is True


def test_tier_definitions():
    """All four tiers should be defined with core + optional proposers."""
    from moa.models import TIERS
    assert "flash" in TIERS
    assert "lite" in TIERS
    assert "pro" in TIERS
    assert "ultra" in TIERS
    assert TIERS["flash"].aggregator is None
    assert TIERS["lite"].aggregator is not None
    assert TIERS["ultra"].aggregator is not None
    assert len(TIERS["lite"].optional_proposers) > 0
    assert len(TIERS["flash"].optional_proposers) == 0


def test_core_tiers_use_3_providers():
    """Core proposers in each tier should only use Anthropic/OpenAI/Google."""
    from moa.models import TIERS
    core_providers = {"Anthropic", "OpenAI", "Google"}
    for name in ("lite", "pro", "ultra"):
        tier = TIERS[name]
        for m in tier.proposers:
            assert m.provider in core_providers, \
                f"Tier '{name}' core proposer {m.name} is {m.provider}, not in core"


def test_ultra_uses_opus():
    """Ultra tier should use Opus as aggregator with Sonnet as a core proposer."""
    from moa.models import TIERS, CLAUDE_OPUS, CLAUDE_SONNET
    assert TIERS["ultra"].aggregator == CLAUDE_OPUS
    assert CLAUDE_SONNET in TIERS["ultra"].proposers


def test_reviewer_roles():
    """Should have 4 specialist reviewer roles with fallbacks."""
    from moa.models import REVIEWER_ROLES
    assert len(REVIEWER_ROLES) == 4
    names = [r.name for r in REVIEWER_ROLES]
    assert "Security Reviewer" in names
    assert "Architecture Reviewer" in names
    assert "Performance Reviewer" in names
    assert "Correctness Reviewer" in names
    for role in REVIEWER_ROLES:
        assert role.fallback is not None


def test_cost_tracking_escalation():
    """QueryCost should track escalation status."""
    from moa.models import QueryCost
    cost = QueryCost(tier="cascade:lite→ultra", escalated=True, models_used=["a", "b"])
    assert "ESCALATED" in cost.summary()
    assert "cascade" in cost.summary()


def test_prompt_formatting():
    """format_proposals should label proposals correctly."""
    from moa.prompts import format_proposals
    result = format_proposals(["Resp A", "Resp B"], ["GPT-5.4", "Gemini"])
    assert "GPT-5.4" in result
    assert "Gemini" in result


def test_model_strengths():
    """All models should have at least one strength defined."""
    from moa.models import ALL_MODELS
    for model in ALL_MODELS:
        assert len(model.strengths) > 0, f"{model.name} has no strengths"


def test_real_cost_calculation():
    """calculate_real_cost should match expected formula."""
    from moa.engine import calculate_real_cost
    from moa.models import GEMINI_FLASH
    # 1000 input tokens, 500 output tokens
    cost = calculate_real_cost(GEMINI_FLASH, 1000, 500)
    expected = (0.15 * 1000 / 1_000_000) + (0.60 * 500 / 1_000_000)
    assert abs(cost - expected) < 0.000001


def test_config_defaults():
    """Config should have sensible defaults."""
    from moa.config import MODEL_TIMEOUT_SECONDS, MAX_DAILY_SPEND_USD, MAX_DIFF_LINES
    assert MODEL_TIMEOUT_SECONDS > 0
    assert MAX_DAILY_SPEND_USD > 0
    assert MAX_DIFF_LINES > 0


@pytest.mark.asyncio
async def test_call_model_handles_failure():
    """call_model should return None after failed attempts."""
    from moa.engine import call_model
    from moa.models import GEMINI_FLASH

    with patch("moa.engine.acompletion", side_effect=Exception("API Error")):
        result = await call_model(
            GEMINI_FLASH, [{"role": "user", "content": "test"}]
        )
        assert result is None


@pytest.mark.asyncio
async def test_call_model_timeout():
    """call_model should return None on timeout."""
    from moa.engine import call_model
    from moa.models import GEMINI_FLASH

    async def slow_response(*args, **kwargs):
        await asyncio.sleep(10)

    with patch("moa.engine.acompletion", side_effect=slow_response):
        result = await call_model(
            GEMINI_FLASH,
            [{"role": "user", "content": "test"}],
            timeout=1,  # 1 second timeout
        )
        assert result is None


@pytest.mark.asyncio
async def test_call_model_returns_real_cost():
    """call_model should include real cost_usd in result."""
    from moa.engine import call_model
    from moa.models import GEMINI_FLASH

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello!"
    mock_response.get = lambda key, default=None: {
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }.get(key, default)

    with patch("moa.engine.acompletion", return_value=mock_response):
        result = await call_model(
            GEMINI_FLASH,
            [{"role": "user", "content": "test"}],
        )
        assert result is not None
        assert "cost_usd" in result
        assert result["cost_usd"] > 0
        assert result["latency_s"] >= 0


def test_core_optional_split():
    """Core and optional model lists should be correct."""
    from moa.models import CORE_MODELS, OPTIONAL_MODELS, ALL_MODELS
    assert len(CORE_MODELS) == 9
    assert len(OPTIONAL_MODELS) == 5
    assert len(ALL_MODELS) == 14
    # Core should only be Anthropic, OpenAI, Google
    for m in CORE_MODELS:
        assert m.provider in ("Anthropic", "OpenAI", "Google")
    # Optional should be everything else
    for m in OPTIONAL_MODELS:
        assert m.provider not in ("Anthropic", "OpenAI", "Google")

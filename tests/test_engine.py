"""Tests for the MoA engine."""

import asyncio
import os
import pytest
from unittest.mock import patch

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
    # Tiers should have optional_proposers field
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


@pytest.mark.asyncio
async def test_call_model_handles_failure():
    """call_model should return None after 3 failed attempts."""
    from moa.engine import call_model
    from moa.models import GEMINI_FLASH

    with patch("moa.engine.acompletion", side_effect=Exception("API Error")):
        result = await call_model(
            GEMINI_FLASH, [{"role": "user", "content": "test"}]
        )
        assert result is None

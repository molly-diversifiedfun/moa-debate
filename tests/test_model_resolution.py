"""Model resolution: roster entries name a FAMILY; the id is resolved at call time.

A dated id retiring (Anthropic 404 not_found_error) must never break moa again:
call_model re-resolves the family and retries once, for every caller.
"""
import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from moa import config, resolve
from moa.models import CLAUDE_HAIKU, CLAUDE_OPUS, CLAUDE_SONNET, GPT_4_1


ANTHROPIC_IDS = [
    "claude-opus-4-20250514", "claude-opus-4-5-20251101", "claude-opus-4-8",
    "claude-opus-5", "claude-opus-5-5", "claude-sonnet-4-5-20250929",
    "claude-sonnet-5", "claude-haiku-4-5-20251001", "claude-fable-5-1",
]
OPENAI_IDS = [
    "gpt-4.1", "gpt-4.1-mini", "gpt-5", "gpt-5-pro", "gpt-5.4", "gpt-5.4-mini",
    "gpt-5.5", "gpt-5.5-pro", "gpt-5.6-luna", "gpt-6-astra", "gpt-5.2-codex",
]


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    for f in ("model-cache.json", "models.yaml"):
        p = config.MOA_HOME / f
        if p.exists():
            p.unlink()
    for k in list(os.environ):
        if k.startswith("MOA_MODEL_"):
            monkeypatch.delenv(k)
    from moa import health
    monkeypatch.setattr(health, "_health_cache", {})
    monkeypatch.setattr(health, "_loaded", True)
    monkeypatch.setattr(health, "_save", lambda: None)


def listing(provider):
    return {"anthropic": ANTHROPIC_IDS, "openai": OPENAI_IDS}[provider]


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ── picking the newest member of a family ────────────────────────────────────

@pytest.mark.parametrize("family,expected", [
    ("anthropic:opus", "anthropic/claude-opus-5-5"),
    ("anthropic:sonnet", "anthropic/claude-sonnet-5"),
    ("anthropic:haiku", "anthropic/claude-haiku-4-5-20251001"),
    # plain gpt-N(.M) only: not -pro, -mini, -codex or named variants like gpt-6-astra
    ("openai:flagship", "gpt-5.5"),
])
def test_newest_member_of_each_family(family, expected):
    assert resolve.pick_newest(family, listing(resolve.FAMILIES[family].provider)) == expected


def test_date_suffix_is_not_read_as_a_minor_version():
    # claude-opus-4-20250514 is 4.0 (dated), older than 4.5
    ids = ["claude-opus-4-20250514", "claude-opus-4-5-20251101"]
    assert resolve.pick_newest("anthropic:opus", ids) == "anthropic/claude-opus-4-5-20251101"


def test_no_member_listed_returns_none():
    assert resolve.pick_newest("anthropic:opus", ["claude-sonnet-5"]) is None


# ── resolve_model: override > fresh cache > listing > stale cache > pinned ─────

def test_unfamilied_model_uses_its_pinned_name():
    assert GPT_4_1.family is None
    assert resolve.resolve_model(GPT_4_1) == (GPT_4_1.name, "pinned")


def test_lists_and_caches():
    with patch.object(resolve, "list_provider_models", side_effect=listing) as lister:
        assert resolve.resolve_model(CLAUDE_OPUS) == ("anthropic/claude-opus-5-5", "listed")
        assert resolve.resolve_model(CLAUDE_OPUS) == ("anthropic/claude-opus-5-5", "cache")
    assert lister.call_count == 1


def test_stale_cache_relists():
    with patch.object(resolve, "list_provider_models", side_effect=listing):
        resolve.resolve_model(CLAUDE_OPUS)
    later = time.time() + 25 * 3600
    with patch.object(resolve.time, "time", return_value=later), \
         patch.object(resolve, "list_provider_models", return_value=["claude-opus-6"]):
        assert resolve.resolve_model(CLAUDE_OPUS) == ("anthropic/claude-opus-6", "listed")


def test_listing_failure_uses_stale_cache_then_pinned():
    with patch.object(resolve, "list_provider_models", side_effect=RuntimeError("down")):
        assert resolve.resolve_model(CLAUDE_SONNET) == (CLAUDE_SONNET.name, "pinned")
    with patch.object(resolve, "list_provider_models", side_effect=listing):
        resolve.resolve_model(CLAUDE_SONNET)
    later = time.time() + 25 * 3600
    with patch.object(resolve.time, "time", return_value=later), \
         patch.object(resolve, "list_provider_models", side_effect=RuntimeError("down")):
        assert resolve.resolve_model(CLAUDE_SONNET) == ("anthropic/claude-sonnet-5", "stale-cache")


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("MOA_MODEL_ANTHROPIC_OPUS", "anthropic/claude-opus-4-8")
    with patch.object(resolve, "list_provider_models", side_effect=AssertionError("must not list")):
        assert resolve.resolve_model(CLAUDE_OPUS) == ("anthropic/claude-opus-4-8", "override")


def test_yaml_override_wins():
    (config.MOA_HOME / "models.yaml").write_text('"anthropic:opus": anthropic/claude-opus-5\n')
    with patch.object(resolve, "list_provider_models", side_effect=AssertionError("must not list")):
        assert resolve.resolve_model(CLAUDE_OPUS) == ("anthropic/claude-opus-5", "override")


def test_retired_id_is_never_resolved_again():
    with patch.object(resolve, "list_provider_models", side_effect=listing):
        resolve.mark_retired(CLAUDE_OPUS, "anthropic/claude-opus-5-5")
        assert resolve.resolve_model(CLAUDE_OPUS) == ("anthropic/claude-opus-5", "listed")


# ── call_model: a 404 retires the id, re-resolves, retries once ───────────────

class NotFound(Exception):
    status_code = 404


def ok(model_name):
    return SimpleNamespace(
        get=lambda k, d=None: {"prompt_tokens": 3, "completion_tokens": 2} if k == "usage" else d,
        choices=[SimpleNamespace(message=SimpleNamespace(content=f"hi from {model_name}"))],
    )


def test_call_model_uses_the_resolved_id():
    from moa import orchestrator
    seen = []

    async def fake(model, **kw):
        seen.append(model)
        return ok(model)
    with patch.object(resolve, "list_provider_models", side_effect=listing), \
         patch.object(orchestrator, "acompletion", side_effect=fake):
        r = run(orchestrator.call_model(CLAUDE_OPUS, [{"role": "user", "content": "x"}]))
    assert seen == ["anthropic/claude-opus-5-5"]
    assert r["model"] == "anthropic/claude-opus-5-5"


def test_call_model_retires_a_404_and_retries_once_with_the_next_id():
    from moa import orchestrator
    seen = []

    async def fake(model, **kw):
        seen.append(model)
        if model == "anthropic/claude-opus-5-5":
            raise NotFound('{"type":"not_found_error","message":"model: claude-opus-5-5"}')
        return ok(model)
    with patch.object(resolve, "list_provider_models", side_effect=listing), \
         patch.object(orchestrator, "acompletion", side_effect=fake):
        r = run(orchestrator.call_model(CLAUDE_OPUS, [{"role": "user", "content": "x"}]))
    assert seen == ["anthropic/claude-opus-5-5", "anthropic/claude-opus-5"]
    assert r["content"] == "hi from anthropic/claude-opus-5"


def test_call_model_does_not_retire_on_429():
    from moa import orchestrator

    class RateLimited(Exception):
        status_code = 429

    async def fake(model, **kw):
        raise RateLimited("rate limited")

    async def no_sleep(_s):
        return None
    with patch.object(resolve, "list_provider_models", side_effect=listing), \
         patch.object(orchestrator, "acompletion", side_effect=fake), \
         patch.object(orchestrator.asyncio, "sleep", side_effect=no_sleep):
        assert run(orchestrator.call_model(CLAUDE_SONNET, [{"role": "user", "content": "x"}])) is None
    assert "anthropic/claude-sonnet-5" not in resolve._load_cache().get("retired", [])


def test_call_model_failure_still_returns_none():
    # the contract ~40 call sites rely on
    from moa import orchestrator

    async def fake(model, **kw):
        raise NotFound("not_found_error")
    with patch.object(resolve, "list_provider_models", side_effect=listing), \
         patch.object(orchestrator, "acompletion", side_effect=fake):
        assert run(orchestrator.call_model(CLAUDE_HAIKU, [{"role": "user", "content": "x"}])) is None


# ── nothing touches the real home ─────────────────────────────────────────────

def test_tests_never_touch_the_real_moa_home():
    import conftest
    real = Path(conftest._original_home) / ".moa"
    assert not str(config.MOA_HOME).startswith(str(real))


# ── newer models reject temperature; health follows the resolved id ──────────

class BadRequest(Exception):
    status_code = 400


def test_temperature_rejected_retries_without_it_and_remembers():
    from moa import orchestrator
    calls = []

    async def fake(model, **kw):
        calls.append(("temperature" in kw, model))
        if "temperature" in kw:
            raise BadRequest('{"type":"invalid_request_error","message":"`temperature` is deprecated for this model."}')
        return ok(model)
    with patch.object(resolve, "list_provider_models", side_effect=listing), \
         patch.object(orchestrator, "acompletion", side_effect=fake):
        r1 = run(orchestrator.call_model(CLAUDE_SONNET, [{"role": "user", "content": "x"}]))
        r2 = run(orchestrator.call_model(CLAUDE_SONNET, [{"role": "user", "content": "x"}]))
    assert r1 and r2
    # first call learns; the second goes straight to the no-temperature form
    assert calls == [(True, "anthropic/claude-sonnet-5"), (False, "anthropic/claude-sonnet-5"),
                     (False, "anthropic/claude-sonnet-5")]


def test_openai_default_only_temperature_is_detected():
    assert resolve.rejects_temperature(BadRequest(
        "Unsupported value: 'temperature' does not support 0.7 with this model. Only the default (1) value is supported."))
    assert not resolve.rejects_temperature(BadRequest("max_tokens is too large"))


def test_old_failures_on_the_roster_name_do_not_block_the_resolved_id():
    from moa import health, orchestrator
    for _ in range(5):
        health.record_failure(CLAUDE_SONNET.name, error_class="RETIRED")

    async def fake(model, **kw):
        return ok(model)
    with patch.object(resolve, "list_provider_models", side_effect=listing), \
         patch.object(orchestrator, "acompletion", side_effect=fake):
        r = run(orchestrator.call_model(CLAUDE_SONNET, [{"role": "user", "content": "x"}]))
    assert r and r["model"] == "anthropic/claude-sonnet-5"

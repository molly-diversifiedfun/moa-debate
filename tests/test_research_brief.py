"""Tests for the multi-agent research-brief mode (moa research)."""

import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


def _make_model(available=True):
    m = MagicMock()
    m.available = available
    m.name = "fake-model"
    return m


def _fake_call_result(content: str, in_tok: int = 100, out_tok: int = 50):
    """Match the call_model return shape that _update_cost expects."""
    return {
        "content": content,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "latency_s": 0.5,
        "model": "fake-model",
        "cost_usd": 0.001,
    }


# ── decompose_query ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_decompose_query_returns_list(monkeypatch):
    """decompose_query parses the JSON {sub_questions: [...]} response."""
    from moa.research import decompose_query

    monkeypatch.setattr("moa.models.CLASSIFIER_MODEL", _make_model())
    monkeypatch.setattr(
        "moa.engine.call_model",
        AsyncMock(return_value=_fake_call_result(
            '{"sub_questions": ["What is X?", "How does Y compare?", "When does Z pay off?"]}'
        )),
    )
    result = await decompose_query("Should I switch from X to Y?")
    assert result == ["What is X?", "How does Y compare?", "When does Z pay off?"]


@pytest.mark.asyncio
async def test_decompose_query_falls_back_on_no_model(monkeypatch):
    """When no classifier is available, returns [query] so caller has a single-q fallback."""
    from moa.research import decompose_query

    monkeypatch.setattr("moa.models.CLASSIFIER_MODEL", _make_model(available=False))
    monkeypatch.setattr("moa.models.CLAUDE_HAIKU", _make_model(available=False))

    result = await decompose_query("a question")
    assert result == ["a question"]


@pytest.mark.asyncio
async def test_decompose_query_falls_back_on_bad_json(monkeypatch):
    """Garbage JSON should not crash — falls back to [query]."""
    from moa.research import decompose_query

    monkeypatch.setattr("moa.models.CLASSIFIER_MODEL", _make_model())
    monkeypatch.setattr(
        "moa.engine.call_model",
        AsyncMock(return_value=_fake_call_result("not json at all")),
    )
    result = await decompose_query("a question")
    assert result == ["a question"]


@pytest.mark.asyncio
async def test_decompose_query_caps_at_five(monkeypatch):
    """Caps sub-questions at 5 even if the model returns more."""
    from moa.research import decompose_query

    monkeypatch.setattr("moa.models.CLASSIFIER_MODEL", _make_model())
    monkeypatch.setattr(
        "moa.engine.call_model",
        AsyncMock(return_value=_fake_call_result(
            json.dumps({"sub_questions": [f"sub-q {i}" for i in range(10)]})
        )),
    )
    result = await decompose_query("a question")
    assert len(result) == 5


@pytest.mark.asyncio
async def test_decompose_query_strips_fenced_json(monkeypatch):
    """Handles models that wrap output in ```json ... ``` fences."""
    from moa.research import decompose_query

    monkeypatch.setattr("moa.models.CLASSIFIER_MODEL", _make_model())
    monkeypatch.setattr(
        "moa.engine.call_model",
        AsyncMock(return_value=_fake_call_result(
            '```json\n{"sub_questions": ["a", "b"]}\n```'
        )),
    )
    result = await decompose_query("q")
    assert result == ["a", "b"]


# ── collect_unique_sources ────────────────────────────────────────────────────

def test_collect_unique_sources_dedupes_by_url():
    """Preserves first-seen order, drops dup URLs and empty URLs."""
    from moa.research import SearchResult, collect_unique_sources

    results = [
        SearchResult(url="https://a.com", title="A", snippet="", content=""),
        SearchResult(url="https://b.com", title="B", snippet="", content=""),
        SearchResult(url="https://a.com", title="A dup", snippet="", content=""),
        SearchResult(url="", title="empty", snippet="", content=""),
        SearchResult(url="https://c.com", title="C", snippet="", content=""),
    ]
    unique = collect_unique_sources(results)
    assert [r.url for r in unique] == ["https://a.com", "https://b.com", "https://c.com"]


# ── run_research_brief — orchestration shape ─────────────────────────────────

@pytest.mark.asyncio
async def test_run_research_brief_orchestrates_plan_workers_synth(monkeypatch):
    """End-to-end orchestration: decompose → parallel workers → final synth.

    Verifies:
    1. decompose_query is called with the original query.
    2. Workers fire once per sub-question.
    3. Final synth receives all worker outputs.
    4. Response shape matches the documented dict.
    """
    from moa.adaptive import run_research_brief

    monkeypatch.setattr("moa.research.get_search_provider", lambda: MagicMock())
    monkeypatch.setattr(
        "moa.research.decompose_query",
        AsyncMock(return_value=["sub-q 1", "sub-q 2", "sub-q 3"]),
    )
    monkeypatch.setattr(
        "moa.research.deep_research",
        AsyncMock(side_effect=lambda q, p, **k: f"ctx for {q}"),
    )

    # Track calls to differentiate worker vs synth invocations.
    call_log: list[dict] = []

    async def fake_call_model(model, messages, **kw):
        call_log.append({"sys": messages[0]["content"]})
        if "ONE sub-question" in messages[0]["content"]:
            return _fake_call_result("## sub-q\n\nworker answer with [1]")
        return _fake_call_result("# Brief\n\n## TL;DR\nFinal brief.", in_tok=500, out_tok=200)

    monkeypatch.setattr("moa.adaptive.call_model", fake_call_model)
    monkeypatch.setattr("moa.adaptive._check_budget_or_raise", lambda: None)
    monkeypatch.setattr("moa.adaptive.record_spend", lambda x: None)

    def fake_get_aggregator(prefer_premium=False):
        m = MagicMock()
        m.name = "anthropic/claude-opus" if prefer_premium else "anthropic/claude-sonnet"
        return m
    monkeypatch.setattr("moa.adaptive.get_aggregator", fake_get_aggregator)

    result = await run_research_brief("Original question?", depth="deep")

    # Response shape
    assert "response" in result
    assert "sub_questions" in result
    assert "worker_outputs" in result
    assert "cost" in result
    assert "latency_ms" in result
    assert result["depth"] == "deep"
    assert result["synthesizer"] == "anthropic/claude-opus"
    assert len(result["sub_questions"]) == 3
    assert len(result["worker_outputs"]) == 3

    # 3 worker calls + 1 synth call = 4 total
    assert len(call_log) == 4
    # The final call (synth) used the brief-synth system prompt
    assert "research brief" in call_log[-1]["sys"].lower()
    # The first 3 used the worker-synth prompt
    for i in range(3):
        assert "ONE sub-question" in call_log[i]["sys"]


@pytest.mark.asyncio
async def test_run_research_brief_raises_without_provider(monkeypatch):
    """If no Firecrawl + no DDG, run_research_brief errors with actionable message."""
    from moa.adaptive import run_research_brief

    monkeypatch.setattr("moa.research.get_search_provider", lambda: None)
    monkeypatch.setattr("moa.adaptive._check_budget_or_raise", lambda: None)

    with pytest.raises(RuntimeError, match="search provider"):
        await run_research_brief("q")


@pytest.mark.asyncio
async def test_run_research_brief_shallow_uses_lite_search(monkeypatch):
    """depth='shallow' calls lite_search instead of deep_research per sub-q."""
    from moa.adaptive import run_research_brief

    monkeypatch.setattr("moa.research.get_search_provider", lambda: MagicMock())
    monkeypatch.setattr(
        "moa.research.decompose_query",
        AsyncMock(return_value=["sub-q 1", "sub-q 2"]),
    )

    lite_mock = AsyncMock(side_effect=lambda q, p, **k: f"lite ctx {q}")
    deep_mock = AsyncMock(side_effect=lambda q, p, **k: f"deep ctx {q}")
    monkeypatch.setattr("moa.research.lite_search", lite_mock)
    monkeypatch.setattr("moa.research.deep_research", deep_mock)

    async def fake_call_model(model, messages, **kw):
        return _fake_call_result("x")

    monkeypatch.setattr("moa.adaptive.call_model", fake_call_model)
    monkeypatch.setattr("moa.adaptive._check_budget_or_raise", lambda: None)
    monkeypatch.setattr("moa.adaptive.record_spend", lambda x: None)
    monkeypatch.setattr(
        "moa.adaptive.get_aggregator",
        lambda prefer_premium=False: MagicMock(name="m"),
    )

    result = await run_research_brief("q", depth="shallow")
    assert result["depth"] == "shallow"
    assert lite_mock.call_count == 2
    assert deep_mock.call_count == 0


@pytest.mark.asyncio
async def test_run_research_brief_raises_when_all_searches_empty(monkeypatch):
    """When EVERY sub-question's research returns nothing, fail fast rather than
    produce an empty brief."""
    from moa.adaptive import run_research_brief

    monkeypatch.setattr("moa.research.get_search_provider", lambda: MagicMock())
    monkeypatch.setattr(
        "moa.research.decompose_query",
        AsyncMock(return_value=["sub-q empty"]),
    )
    monkeypatch.setattr("moa.research.deep_research", AsyncMock(return_value=None))
    monkeypatch.setattr("moa.adaptive._check_budget_or_raise", lambda: None)

    with pytest.raises(RuntimeError, match="no results"):
        await run_research_brief("q")


@pytest.mark.asyncio
async def test_run_research_brief_pools_context_across_workers(monkeypatch):
    """Each worker should see the FULL pooled research, not just its own sub-q's
    search results. Regression for the original bug: a 'compare X to Y' sub-question
    couldn't compare because it only saw the 'compare' search results, not the
    sibling 'X features' / 'Y features' results."""
    from moa.adaptive import run_research_brief

    monkeypatch.setattr("moa.research.get_search_provider", lambda: MagicMock())
    monkeypatch.setattr(
        "moa.research.decompose_query",
        AsyncMock(return_value=["What is X?", "What is Y?", "How do X and Y compare?"]),
    )
    # Each sub-q gets its own distinctive context substring
    async def fake_deep(q, p, **k):
        if "What is X" in q:
            return "FACTS_ABOUT_X here"
        if "What is Y" in q:
            return "FACTS_ABOUT_Y here"
        return "COMPARISON_HINT here"
    monkeypatch.setattr("moa.research.deep_research", fake_deep)

    seen_user_messages: list[str] = []

    async def fake_call_model(model, messages, **kw):
        user = messages[1]["content"]
        if "ONE sub-question" in messages[0]["content"]:
            seen_user_messages.append(user)
        return _fake_call_result("worker answer with [1]")

    monkeypatch.setattr("moa.adaptive.call_model", fake_call_model)
    monkeypatch.setattr("moa.adaptive._check_budget_or_raise", lambda: None)
    monkeypatch.setattr("moa.adaptive.record_spend", lambda x: None)
    monkeypatch.setattr(
        "moa.adaptive.get_aggregator",
        lambda prefer_premium=False: MagicMock(name="m"),
    )

    await run_research_brief("Compare X and Y")

    # All 3 workers should have seen ALL 3 fragments in their research material
    assert len(seen_user_messages) == 3
    for msg in seen_user_messages:
        assert "FACTS_ABOUT_X" in msg, "worker missed pooled X facts"
        assert "FACTS_ABOUT_Y" in msg, "worker missed pooled Y facts"
        assert "COMPARISON_HINT" in msg, "worker missed pooled compare hint"

"""Tests for research-augmented routing."""

import os
import pytest

from moa.research import (
    SearchResult,
    FirecrawlProvider,
    format_research_context,
    get_search_provider,
)


# ── SearchResult dataclass ────────────────────────────────────────────────────

def test_search_result_fields():
    """SearchResult has expected fields."""
    r = SearchResult(url="https://example.com", title="Test", snippet="A snippet", content="# Content")
    assert r.url == "https://example.com"
    assert r.title == "Test"
    assert r.snippet == "A snippet"
    assert r.content == "# Content"


# ── format_research_context ───────────────────────────────────────────────────

def test_format_research_context_basic():
    """Formats results with header, titles, and sources."""
    results = [
        SearchResult(url="https://a.com", title="Page A", snippet="", content="Content A"),
        SearchResult(url="https://b.com", title="Page B", snippet="", content="Content B"),
    ]
    ctx = format_research_context(results, max_chars=4096)
    assert "reference material may be relevant" in ctx
    assert "### Page A" in ctx
    assert "Source: https://a.com" in ctx
    assert "### Page B" in ctx
    assert "Content A" in ctx
    assert "Content B" in ctx


def test_format_research_context_empty():
    """Returns empty string for no results."""
    assert format_research_context([]) == ""
    assert format_research_context([], max_chars=100) == ""


def test_format_research_context_respects_char_cap():
    """Truncates when total exceeds max_chars."""
    results = [
        SearchResult(url="https://a.com", title="A", snippet="", content="x" * 3000),
        SearchResult(url="https://b.com", title="B", snippet="", content="y" * 3000),
    ]
    ctx = format_research_context(results, max_chars=500)
    assert len(ctx) <= 700  # header + one truncated result
    assert "### A" in ctx


def test_format_research_context_includes_header():
    """Header tells models to reason independently."""
    results = [SearchResult(url="https://a.com", title="A", snippet="", content="test")]
    ctx = format_research_context(results)
    assert "reason independently" in ctx
    assert "not assume" in ctx


# ── get_search_provider ───────────────────────────────────────────────────────

def test_get_search_provider_no_key(monkeypatch):
    """Falls back to DuckDuckGo when FIRECRAWL_API_KEY not set."""
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    from moa.research import DuckDuckGoProvider
    provider = get_search_provider()
    # Should fall back to DuckDuckGo (free, no key needed)
    assert isinstance(provider, DuckDuckGoProvider)


def test_get_search_provider_with_key(monkeypatch):
    """Returns FirecrawlProvider when key is set."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")
    provider = get_search_provider()
    assert provider is not None
    assert isinstance(provider, FirecrawlProvider)
    assert provider.api_key == "fc-test-key"


# ── Mock provider for integration-style tests ────────────────────────────────

class MockSearchProvider:
    """Mock that returns canned results without hitting any API."""

    def __init__(self, results=None):
        self._results = results or []
        self.search_calls = []

    async def search(self, query, max_results=3):
        self.search_calls.append(query)
        return self._results[:max_results]

    async def extract(self, url):
        return f"# Extracted from {url}"


@pytest.mark.asyncio
async def test_lite_search_returns_none_on_empty(monkeypatch):
    """lite_search returns None when provider returns no results."""
    from moa.research import lite_search

    # Mock derive_search_queries to avoid model call
    async def mock_derive(query):
        return [query]

    monkeypatch.setattr("moa.research.derive_search_queries", mock_derive)

    provider = MockSearchProvider(results=[])
    result = await lite_search("test query", provider)
    assert result is None


@pytest.mark.asyncio
async def test_lite_search_returns_context(monkeypatch):
    """lite_search returns formatted context when provider returns results."""
    from moa.research import lite_search

    async def mock_derive(query):
        return ["search 1", "search 2"]

    monkeypatch.setattr("moa.research.derive_search_queries", mock_derive)

    provider = MockSearchProvider(results=[
        SearchResult(url="https://docs.example.com", title="Official Docs", snippet="", content="Use `config.init()` to set up."),
    ])
    result = await lite_search("how to configure", provider)
    assert result is not None
    assert "Official Docs" in result
    assert "config.init()" in result
    assert len(provider.search_calls) == 2  # Called for each derived query


@pytest.mark.asyncio
async def test_lite_search_deduplicates_urls(monkeypatch):
    """lite_search deduplicates results by URL."""
    from moa.research import lite_search

    async def mock_derive(query):
        return ["q1", "q2"]

    monkeypatch.setattr("moa.research.derive_search_queries", mock_derive)

    same_result = SearchResult(url="https://same.com", title="Same", snippet="", content="Same content")
    provider = MockSearchProvider(results=[same_result])

    result = await lite_search("test", provider)
    assert result is not None
    # Should only appear once despite being returned by both queries
    assert result.count("### Same") == 1

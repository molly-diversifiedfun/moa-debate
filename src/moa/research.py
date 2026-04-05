"""Research-augmented routing: web search for grounding model responses."""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import List, Optional, Callable, Protocol

from .config import RESEARCH_CONTEXT_MAX_CHARS_LITE, RESEARCH_CONTEXT_MAX_CHARS_DEEP


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """A single web search result with extracted content."""
    url: str
    title: str
    snippet: str
    content: str  # extracted markdown


# ── SearchProvider protocol ───────────────────────────────────────────────────

class SearchProvider(Protocol):
    """Abstract interface for web search. Swap implementations without changing engine."""

    async def search(self, query: str, max_results: int = 3) -> List[SearchResult]: ...

    async def extract(self, url: str) -> str: ...


# ── Firecrawl implementation ─────────────────────────────────────────────────

class FirecrawlProvider:
    """SearchProvider backed by Firecrawl API (firecrawl-py SDK)."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 3) -> List[SearchResult]:
        """Search via firecrawl-py v2. Returns results with markdown content included."""
        from firecrawl import FirecrawlApp
        from firecrawl.v2.types import ScrapeOptions

        app = FirecrawlApp(api_key=self.api_key)
        loop = asyncio.get_event_loop()

        try:
            resp = await loop.run_in_executor(
                None,
                lambda: app.search(
                    query,
                    limit=max_results,
                    scrape_options=ScrapeOptions(formats=["markdown"]),
                ),
            )
        except Exception:
            return []

        results = []
        for doc in resp.web or []:
            metadata = doc.metadata or {}
            # v2 API: Document has .markdown, .metadata (with sourceURL, title, description)
            results.append(SearchResult(
                url=getattr(metadata, "source_url", "") or getattr(metadata, "sourceURL", "") or "",
                title=getattr(metadata, "title", "") or "",
                snippet=getattr(metadata, "description", "") or "",
                content=(doc.markdown or "")[:4096],
            ))
        return results

    async def extract(self, url: str) -> str:
        """Extract clean markdown from a single URL."""
        from firecrawl import FirecrawlApp

        app = FirecrawlApp(api_key=self.api_key)
        loop = asyncio.get_event_loop()

        try:
            result = await loop.run_in_executor(
                None,
                lambda: app.scrape(url, formats=["markdown"]),
            )
            return result.markdown or ""
        except Exception:
            return ""


# ── Provider factory ──────────────────────────────────────────────────────────

def get_search_provider() -> Optional[SearchProvider]:
    """Return configured search provider, or None if no API key."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return None
    return FirecrawlProvider(api_key)


# ── Search query derivation ──────────────────────────────────────────────────

async def derive_search_queries(query: str) -> List[str]:
    """Use a cheap model to derive 2-3 focused search queries from a question."""
    from .models import CLASSIFIER_MODEL, CLAUDE_HAIKU
    from .engine import call_model
    from .prompts import SEARCH_QUERY_DERIVATION_PROMPT

    model = CLASSIFIER_MODEL if CLASSIFIER_MODEL.available else CLAUDE_HAIKU
    if not model or not model.available:
        return [query]

    result = await call_model(
        model,
        [
            {"role": "system", "content": SEARCH_QUERY_DERIVATION_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0.0,
        max_tokens=200,
        timeout=10,
    )

    if not result:
        return [query]

    try:
        text = result["content"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        queries = parsed.get("queries", [query])
        return queries[:3]
    except (json.JSONDecodeError, KeyError, AttributeError):
        return [query]


# ── Lite search ───────────────────────────────────────────────────────────────

async def lite_search(query: str, provider: SearchProvider) -> Optional[str]:
    """Single-round search: derive queries -> search -> format context.

    Returns formatted research context string, or None on failure.
    """
    try:
        queries = await derive_search_queries(query)
        all_results: List[SearchResult] = []

        for q in queries[:2]:
            results = await provider.search(q, max_results=2)
            all_results.extend(results)

        if not all_results:
            return None

        seen_urls: set = set()
        unique = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique.append(r)

        return format_research_context(unique, max_chars=RESEARCH_CONTEXT_MAX_CHARS_LITE)
    except Exception:
        return None


# ── Deep research ─────────────────────────────────────────────────────────────

async def deep_research(
    query: str,
    provider: SearchProvider,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """Multi-hop research: derive -> search -> identify gaps -> search again -> compile."""
    try:
        # Round 1
        queries = await derive_search_queries(query)
        all_results: List[SearchResult] = []
        for q in queries[:3]:
            results = await provider.search(q, max_results=3)
            all_results.extend(results)

        if on_progress:
            on_progress(f"Searched {len(all_results)} sources...")

        if not all_results:
            return None

        # Identify gaps
        context_so_far = format_research_context(all_results, max_chars=6000)
        gap_queries = await _identify_gaps(query, context_so_far)

        if gap_queries and on_progress:
            on_progress(f"Found {len(gap_queries)} gaps, searching deeper...")

        # Round 2
        for q in gap_queries[:2]:
            results = await provider.search(q, max_results=2)
            all_results.extend(results)

        # Deduplicate
        seen_urls: set = set()
        unique = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique.append(r)

        if on_progress:
            on_progress(f"Compiled {len(unique)} sources, synthesizing...")

        return format_research_context(unique, max_chars=RESEARCH_CONTEXT_MAX_CHARS_DEEP)
    except Exception:
        return None


async def _identify_gaps(query: str, context: str) -> List[str]:
    """Use cheap model to identify what's missing from current research."""
    from .models import CLASSIFIER_MODEL, CLAUDE_HAIKU
    from .engine import call_model
    from .prompts import IDENTIFY_GAPS_PROMPT

    model = CLASSIFIER_MODEL if CLASSIFIER_MODEL.available else CLAUDE_HAIKU
    if not model or not model.available:
        return []

    result = await call_model(
        model,
        [
            {"role": "system", "content": IDENTIFY_GAPS_PROMPT},
            {"role": "user", "content": f"Original question: {query}\n\nResearch so far:\n{context}"},
        ],
        temperature=0.0,
        max_tokens=200,
        timeout=10,
    )

    if not result:
        return []

    try:
        text = result["content"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        return parsed.get("queries", [])[:3]
    except (json.JSONDecodeError, KeyError, AttributeError):
        return []


# ── Context formatting ────────────────────────────────────────────────────────

def format_research_context(results: List[SearchResult], max_chars: int = 4096) -> str:
    """Format search results into a reference context block for model injection."""
    if not results:
        return ""

    parts = []
    total = 0
    for r in results:
        section = f"### {r.title}\nSource: {r.url}\n\n{r.content}"
        if total + len(section) > max_chars:
            remaining = max_chars - total
            if remaining > 200:
                parts.append(section[:remaining] + "...")
            break
        parts.append(section)
        total += len(section)

    if not parts:
        return ""

    header = (
        "The following reference material may be relevant to the question. "
        "Use it if applicable, but reason independently. Do not assume this "
        "information is complete or authoritative."
    )
    return f"{header}\n\n" + "\n\n---\n\n".join(parts)

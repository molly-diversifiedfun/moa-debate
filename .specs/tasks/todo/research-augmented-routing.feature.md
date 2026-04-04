# Spec: Research-Augmented Routing

**Brief:** `docs/briefs/research-augmented-routing-brief.md`
**Exploration:** `docs/explorations/research-augmented-routing-exploration.md`
**Approach:** B — New module (`src/moa/research.py`)
**Status:** Ready for implementation

---

## Summary

Add web search to MOA's adaptive routing. When models disagree (low Jaccard similarity), automatically search the web for reference material, inject it as context, and re-ask. Also add a manual `--research deep` mode for thorough multi-hop research with a single frontier model.

## Dependencies

- `firecrawl-py` SDK (new dependency in pyproject.toml)
- `FIRECRAWL_API_KEY` environment variable

## Implementation Tasks

### Task 1: Add firecrawl-py dependency
**File:** `pyproject.toml`
**Change:** Add `firecrawl-py>=1.0.0` to dependencies list.

### Task 2: Create src/moa/research.py
**File:** `src/moa/research.py` (~200 lines)

#### 2a: SearchProvider protocol + SearchResult dataclass

```python
from dataclasses import dataclass
from typing import Protocol, List, Optional, Callable

@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    content: str  # extracted markdown

class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int = 3) -> List[SearchResult]: ...
    async def extract(self, url: str) -> str: ...
```

#### 2b: FirecrawlProvider implementation

```python
class FirecrawlProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 3) -> List[SearchResult]:
        """Search via firecrawl-py SDK. Returns results with markdown content included."""
        from firecrawl import FirecrawlApp, ScrapeOptions
        app = FirecrawlApp(api_key=self.api_key)
        # Run sync SDK call in executor to avoid blocking
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: app.search(query, limit=max_results,
                               scrape_options=ScrapeOptions(formats=["markdown"]))
        )
        return [
            SearchResult(
                url=r.get("url", ""),
                title=r.get("metadata", {}).get("title", ""),
                snippet=r.get("metadata", {}).get("description", ""),
                content=r.get("markdown", "")[:4096],  # cap per-result
            )
            for r in (resp.get("data") or [])
        ]

    async def extract(self, url: str) -> str:
        """Extract clean markdown from a URL. Used by deep research for follow-ups."""
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=self.api_key)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: app.scrape_url(url, formats=["markdown"])
        )
        return result.get("markdown", "")
```

#### 2c: get_search_provider() factory

```python
import os

def get_search_provider() -> Optional[SearchProvider]:
    """Return configured search provider, or None if no API key."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return None
    return FirecrawlProvider(api_key)
```

#### 2d: derive_search_queries()

```python
from .models import CLAUDE_HAIKU, CLASSIFIER_MODEL
from .engine import call_model
from .prompts import SEARCH_QUERY_DERIVATION_PROMPT

async def derive_search_queries(query: str) -> List[str]:
    """Use a cheap model to derive 2-3 focused search queries from a natural language question."""
    model = CLASSIFIER_MODEL if CLASSIFIER_MODEL.available else CLAUDE_HAIKU
    if not model or not model.available:
        # Fallback: use the original query as-is
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
        import json
        text = result["content"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        queries = parsed.get("queries", [query])
        return queries[:3]  # Cap at 3
    except (json.JSONDecodeError, KeyError):
        return [query]
```

#### 2e: lite_search()

```python
async def lite_search(query: str, provider: SearchProvider) -> Optional[str]:
    """Single-round search: derive queries → search → format context.

    Returns formatted research context string, or None if search fails/empty.
    """
    try:
        queries = await derive_search_queries(query)
        all_results: List[SearchResult] = []
        for q in queries[:2]:  # Max 2 search calls
            results = await provider.search(q, max_results=2)
            all_results.extend(results)

        if not all_results:
            return None

        # Deduplicate by URL
        seen_urls = set()
        unique = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique.append(r)

        return format_research_context(unique, max_chars=4096)
    except Exception:
        return None  # Fallback to existing behavior
```

#### 2f: deep_research()

```python
async def deep_research(
    query: str,
    provider: SearchProvider,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """Multi-hop research: derive → search → identify gaps → search again → compile.

    Returns compiled research context string for single-model synthesis.
    """
    try:
        # Round 1: Initial search
        queries = await derive_search_queries(query)
        all_results: List[SearchResult] = []
        for q in queries[:3]:
            results = await provider.search(q, max_results=3)
            all_results.extend(results)

        if on_progress:
            on_progress(f"Searched {len(all_results)} sources...")

        if not all_results:
            return None

        # Identify gaps using cheap model
        context_so_far = format_research_context(all_results, max_chars=6000)
        gap_queries = await _identify_gaps(query, context_so_far)

        if gap_queries and on_progress:
            on_progress(f"Found {len(gap_queries)} gaps, searching deeper...")

        # Round 2: Follow-up searches
        for q in gap_queries[:2]:
            results = await provider.search(q, max_results=2)
            all_results.extend(results)

        # Deduplicate
        seen_urls = set()
        unique = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique.append(r)

        if on_progress:
            on_progress(f"Compiled {len(unique)} sources, synthesizing...")

        return format_research_context(unique, max_chars=12288)
    except Exception:
        return None


async def _identify_gaps(query: str, context: str) -> List[str]:
    """Use cheap model to identify what's missing from current research."""
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
        import json
        text = result["content"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        return parsed.get("queries", [])[:3]
    except (json.JSONDecodeError, KeyError):
        return []
```

#### 2g: format_research_context()

```python
def format_research_context(results: List[SearchResult], max_chars: int = 4096) -> str:
    """Format search results into a reference context block for model injection."""
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
```

### Task 3: Add prompts to prompts.py
**File:** `src/moa/prompts.py`

```python
SEARCH_QUERY_DERIVATION_PROMPT = """Given a user's question, derive 2-3 focused web search queries \
that would find authoritative documentation, official docs, or technical references to help answer it.

Rules:
- Make queries specific and technical (not the original question verbatim)
- Target official documentation, GitHub repos, RFCs, or authoritative sources
- If the question mentions a specific tool/library/framework, include its name

Respond with ONLY a JSON object:
{"queries": ["search query 1", "search query 2"]}"""


IDENTIFY_GAPS_PROMPT = """You have initial research for a question. Identify what's still \
missing or unclear that would require additional searches.

Rules:
- Only suggest follow-up queries if there are genuine gaps
- Target specific missing details, not broad topics
- If the research is sufficient, return an empty list

Respond with ONLY a JSON object:
{"queries": ["follow-up query 1", "follow-up query 2"]}"""


DEEP_RESEARCH_SYNTHESIS_PROMPT = """You are answering a question using research gathered \
from web sources. The research context is provided below.

Rules:
- Ground your answer in the provided sources
- Cite sources by name/URL when making specific claims
- If sources conflict, note the conflict and reason about which is more authoritative
- If the research doesn't fully answer the question, say what's still uncertain
- Be specific and technical — the user chose deep research because they need precision"""
```

### Task 4: Modify engine.py — disagreement branch
**File:** `src/moa/engine.py`
**Location:** Line 541, the `else` branch of `if agreement["consensus"]`

Replace the current disagreement branch with:

```python
    else:
        # Disagreement → try research-augmented re-ask, then fall back to attribution synthesis
        research_context = None
        if research_mode != "off":
            from .research import lite_search, get_search_provider
            provider = get_search_provider()
            if provider:
                research_context = await lite_search(query, provider)

        if research_context:
            # Re-run proposers with research context
            augmented_query = f"[REFERENCE CONTEXT]\n{research_context}\n[/REFERENCE CONTEXT]\n\n{query}"
            augmented_msg = [{"role": "user", "content": augmented_query}]
            re_tasks = [call_model(m, augmented_msg) for m in available]
            re_results = await asyncio.gather(*re_tasks)

            re_proposals = []
            re_model_names = []
            for model, r in zip(available, re_results):
                short = model.name.split("/")[-1] if "/" in model.name else model.name
                if r:
                    re_proposals.append(r["content"])
                    re_model_names.append(short)
                    _update_cost(cost, r)
                    model_status[f"{short}:re"] = f"✅ {r['latency_s']}s"

            if re_proposals:
                proposals = re_proposals
                model_names = re_model_names
                cost.tier += "+research"

        # Synthesize (same as before — works whether we re-asked or not)
        if synthesizer:
            synth_prompt = DISAGREEMENT_SYNTHESIS_PROMPT.format(
                query=query,
                proposals=format_proposals(proposals, model_names)
            )
            # ... (existing synthesizer call unchanged)
```

Also add `research_mode="auto"` parameter to `run_adaptive()` signature.

### Task 5: Add deep research flow to engine.py
**File:** `src/moa/engine.py`

New function:

```python
async def run_deep_research(query: str) -> Dict[str, Any]:
    """Deep research mode: multi-hop search → single frontier model synthesis."""
    from .research import deep_research, get_search_provider
    from .prompts import DEEP_RESEARCH_SYNTHESIS_PROMPT
    from .models import CLAUDE_OPUS, GPT_5_4, get_aggregator

    _check_budget_or_raise()
    start = time.monotonic()
    cost = QueryCost(tier="deep-research")

    provider = get_search_provider()
    if not provider:
        raise RuntimeError("Deep research requires FIRECRAWL_API_KEY. Set it in .env or environment.")

    progress_updates = []
    def on_progress(msg):
        progress_updates.append(msg)

    context = await deep_research(query, provider, on_progress=on_progress)
    if not context:
        raise RuntimeError("Research produced no results. Try rephrasing the query.")

    # Single frontier model with full context
    model = get_aggregator(prefer_premium=True)  # Opus preferred
    messages = [
        {"role": "system", "content": DEEP_RESEARCH_SYNTHESIS_PROMPT},
        {"role": "user", "content": f"[RESEARCH CONTEXT]\n{context}\n[/RESEARCH CONTEXT]\n\nQuestion: {query}"},
    ]

    result = await call_model(model, messages, temperature=0.2, timeout=AGGREGATOR_TIMEOUT_SECONDS)
    if not result:
        raise RuntimeError("Synthesis model failed.")

    _update_cost(cost, result, is_aggregator=True)
    elapsed = int((time.monotonic() - start) * 1000)
    record_spend(cost.estimated_cost_usd)

    return {
        "response": result["content"],
        "model_status": {model.name.split("/")[-1]: f"✅ {result['latency_s']}s"},
        "cost": cost,
        "latency_ms": elapsed,
        "research_steps": progress_updates,
    }
```

### Task 6: Add --research flag to CLI
**File:** `src/moa/cli.py`

Add parameter to `ask()`:

```python
research: str = typer.Option(
    "auto", "--research", "-R",
    help="Research mode: auto (search on disagreement), lite (force search), deep (multi-hop), off"
),
```

Add handling:

```python
if research == "deep":
    from .engine import run_deep_research
    with console.status("[bold cyan]Deep research (searching → reading → synthesizing)...[/bold cyan]"):
        result = asyncio.run(run_deep_research(query))
    # Display with source citations
elif cascade:
    # existing cascade
elif adaptive:
    result = asyncio.run(run_adaptive(query, research_mode=research))
    # existing display
```

### Task 7: Update config + env
**Files:** `src/moa/config.py`, `.env.example`

```python
# config.py
RESEARCH_CONTEXT_MAX_CHARS_LITE = 4096
RESEARCH_CONTEXT_MAX_CHARS_DEEP = 12288
```

```bash
# .env.example
FIRECRAWL_API_KEY=fc-your-key-here  # Optional: enables research-augmented routing
```

### Task 8: Tests
**File:** `tests/test_research.py`

Test cases:
1. `test_format_research_context` — formats results, respects char cap
2. `test_format_research_context_empty` — returns empty string for no results
3. `test_derive_search_queries_fallback` — returns original query when model unavailable
4. `test_lite_search_fallback` — returns None when provider fails
5. `test_get_search_provider_no_key` — returns None without API key
6. `test_get_search_provider_with_key` — returns FirecrawlProvider with key
7. `test_search_result_dataclass` — fields exist and are correct types
8. `test_deep_research_no_provider` — raises RuntimeError

Mock `SearchProvider` for all tests — no real Firecrawl calls.

### Task 9: Update CLAUDE.md
**File:** `CLAUDE.md`

Add `research.py` to module map. Add `--research` flag to commands. Note `FIRECRAWL_API_KEY` dependency.

---

## File Change Summary

| File | Change | Lines |
|------|--------|-------|
| `pyproject.toml` | Add `firecrawl-py` dependency | +1 |
| `src/moa/research.py` | **New** — SearchProvider, Firecrawl, lite_search, deep_research | ~200 |
| `src/moa/prompts.py` | Add 3 prompt templates | ~30 |
| `src/moa/engine.py` | Modify disagreement branch + add `run_deep_research()` | ~50 |
| `src/moa/cli.py` | Add `--research` flag + deep research display | ~15 |
| `src/moa/config.py` | Add research context char limits | +3 |
| `.env.example` | Add `FIRECRAWL_API_KEY` | +1 |
| `tests/test_research.py` | **New** — 8 test cases with mock provider | ~80 |
| `CLAUDE.md` | Update module map + commands | ~10 |

**Total:** ~390 new/modified lines across 9 files

## Acceptance Criteria

- [ ] `moa ask "niche question"` auto-searches when models disagree (lite search)
- [ ] `moa ask --research deep "question"` runs multi-hop search + single-model synthesis
- [ ] `moa ask --research off "question"` disables research (existing behavior)
- [ ] Research gracefully falls back when: no API key, search fails, no results
- [ ] Cost tracking includes search query derivation model calls
- [ ] Source citations appear in deep research output
- [ ] `pytest tests/test_research.py` passes with mock provider
- [ ] No real API calls in tests

# Exploration: Research-Augmented Routing

**Date:** 2026-04-04
**Phase:** Engineer exploration (Phase 2)
**Brief:** `docs/briefs/research-augmented-routing-brief.md`

## Codebase Analysis

### Integration Point
The research step inserts at `engine.py:541` — the `else` branch of `agreement["consensus"]` in `run_adaptive()`. Current flow:

```python
if agreement["consensus"]:
    # synthesize normally
else:
    # DISAGREEMENT_SYNTHESIS_PROMPT → synthesizer
    # THIS is where research goes
```

### Existing Patterns to Reuse
- `call_model()` — already handles retries, timeouts, cost tracking
- `classify_query()` — uses Haiku/Flash for cheap classification; same pattern for search query derivation
- `build_context()` in `context.py` — already handles context injection with truncation; extend for research context
- `QueryCost` — already tracks multi-step costs; add research step costs
- Provider semaphores — search provider doesn't need these (no LiteLLM), but should respect budget

### New Files Needed
- `src/moa/research.py` — SearchProvider protocol + Firecrawl implementation + search query derivation + deep research orchestration

### CLI Changes
- Add `--research` flag to `ask` command: `none` (default auto), `lite` (force), `deep`, `off`
- Deep research gets its own progress display

---

## Approach A: Minimal — Inline in engine.py

**How:** Add research logic directly into `run_adaptive()`'s disagreement branch. No new files, no abstraction.

```python
# engine.py, line 541 (disagreement branch)
else:
    # NEW: research-augmented re-ask
    search_queries = await derive_search_queries(query)  # Haiku call
    search_results = await firecrawl_search(search_queries)  # HTTP call
    if search_results:
        research_context = format_research(search_results)
        augmented_query = f"[REFERENCE CONTEXT]\n{research_context}\n[/REFERENCE CONTEXT]\n\n{query}"
        # Re-run proposers with context
        tasks = [call_model(m, [{"role": "user", "content": augmented_query}]) for m in available]
        results = await asyncio.gather(*tasks)
        # ... re-evaluate agreement, synthesize
    else:
        # Fallback: existing disagreement synthesis
```

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Fastest to ship (~2 hours) | engine.py already 809 lines, adds ~80 more |
| No new abstractions to maintain | Firecrawl API calls mixed into engine logic |
| Easy to understand — all in one place | Can't swap search providers without editing engine |
| | Deep research would need a separate function anyway |
| | No reuse path for other features that want search |

**Verdict:** Gets lite search working fast. But deep research + provider swapping will force a refactor later.

---

## Approach B: New Module — src/moa/research.py

**How:** Create `research.py` with a `SearchProvider` protocol, Firecrawl implementation, and two orchestration functions (`lite_search`, `deep_research`). Engine calls into research module.

```python
# research.py
from typing import Protocol, List

class SearchResult:
    url: str
    title: str
    snippet: str
    content: str  # extracted markdown (filled by extract())

class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int = 3) -> List[SearchResult]: ...
    async def extract(self, url: str) -> str: ...

class FirecrawlProvider:
    """Firecrawl implementation of SearchProvider."""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.firecrawl.dev/v1"
    
    async def search(self, query, max_results=3): ...
    async def extract(self, url): ...

async def derive_search_queries(query: str, model: ModelConfig) -> List[str]:
    """Use a cheap model to derive 2-3 focused search queries."""
    ...

async def lite_search(query: str, provider: SearchProvider) -> Optional[str]:
    """Single-round search: derive queries → search → format context."""
    queries = await derive_search_queries(query, CLAUDE_HAIKU)
    results = []
    for q in queries[:2]:
        results.extend(await provider.search(q, max_results=2))
    return format_research_context(results, max_chars=4096)

async def deep_research(query: str, provider: SearchProvider, on_progress=None) -> str:
    """Multi-hop search: derive → search → identify gaps → search again → compile."""
    # Round 1
    queries = await derive_search_queries(query, CLAUDE_HAIKU)
    results = await _search_and_extract(provider, queries)
    if on_progress: on_progress("Searched 3 sources...")
    
    # Identify gaps
    gaps = await _identify_gaps(query, results)
    if on_progress: on_progress(f"Found {len(gaps)} gaps, searching deeper...")
    
    # Round 2
    gap_results = await _search_and_extract(provider, gaps)
    results.extend(gap_results)
    
    # Compile
    return format_research_context(results, max_chars=12288)
```

```python
# engine.py changes (~15 lines)
from .research import lite_search, get_search_provider

async def run_adaptive(query, research_mode="auto"):
    ...
    if not agreement["consensus"]:
        if research_mode != "off":
            provider = get_search_provider()
            if provider:
                context = await lite_search(query, provider)
                if context:
                    # Re-run proposers with context
                    augmented = f"[REFERENCE CONTEXT]\n{context}\n[/REFERENCE CONTEXT]\n\n{query}"
                    # ... re-propose and re-evaluate
        # Existing disagreement synthesis as fallback
```

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Clean separation — engine doesn't know about Firecrawl | One more file to maintain |
| Provider-agnostic from day one | Slightly more code upfront |
| Deep research reuses same provider/queries | Protocol might be over-engineered for 1 provider |
| Testable in isolation (mock SearchProvider) | |
| engine.py stays focused on orchestration | |

**Verdict:** Right level of abstraction. Protocol pays for itself when we add deep research. Testable. Recommended.

---

## Approach C: Event-Driven — Hook-Based Architecture

**How:** Instead of modifying engine.py, add research as a hook/middleware that intercepts disagreement events. Engine emits events, research module subscribes.

```python
# Engine emits:
event_bus.emit("disagreement", {
    "query": query,
    "proposals": proposals,
    "agreement_score": agreement["score"],
})

# Research module subscribes:
@event_bus.on("disagreement")
async def research_on_disagreement(event):
    context = await lite_search(event["query"])
    event_bus.emit("research_complete", {"context": context})
```

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Engine untouched — zero coupling | WAY over-engineered for this |
| Could add other reactions to disagreement | Event bus doesn't exist, would need to build |
| Extensible | Async event coordination is complex |
| | Debugging becomes harder (implicit flow) |
| | Deep research doesn't fit event pattern (it's not reactive) |

**Verdict:** Over-engineered. We're adding one feature to one code path. An event bus is a solution looking for a problem.

---

## Recommendation: Approach B

**Why:**
1. Right level of abstraction — not too much (event bus), not too little (inline)
2. Provider protocol costs ~10 lines and pays for itself immediately (Firecrawl today, anything tomorrow)
3. `research.py` contains all search logic — engine.py adds ~15 lines, not 80
4. Deep research is a natural extension of the same module
5. Mock `SearchProvider` makes testing trivial — no Firecrawl API calls in CI
6. Matches existing codebase patterns (each concern in its own module)

**Implementation plan:**
1. Create `src/moa/research.py` (SearchProvider protocol, FirecrawlProvider, derive_search_queries, lite_search, deep_research)
2. Add `SEARCH_QUERY_DERIVATION_PROMPT` to `prompts.py`
3. Modify `engine.py:run_adaptive()` disagreement branch (~15 lines)
4. Add `--research` flag to `cli.py:ask()` command
5. Add `FIRECRAWL_API_KEY` to config/env loading
6. Add tests: mock SearchProvider, test lite_search flow, test fallback on search failure
7. Update CLAUDE.md with new module

**Estimated new code:** ~200 lines in research.py, ~15 in engine.py, ~10 in cli.py, ~20 in prompts.py, ~80 in tests

**Open questions resolved:**
- Same proposers on re-ask (controlled comparison)
- Deep research caching: defer to v2
- Context caps: 4K lite, 12K deep, hardcoded for v1

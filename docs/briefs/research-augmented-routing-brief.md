# Product Brief: Research-Augmented Routing

**Date:** 2026-04-04
**Author:** Product-lead
**Status:** Draft (post devil's advocate)

## Problem

When MOA's adaptive routing hits low model agreement, it escalates to premium models. But on **niche/tooling topics** (Claude Code config, specific library APIs, framework-specific patterns), all models are equally uninformed. Escalation doesn't help — it just amplifies confident guessing at higher cost.

**Evidence:** Today's session. Asked MOA to recommend Claude Code project configuration. Escalated to ultra ($0.057). Response got multiple Claude Code specifics wrong (invented settings.json fields, wrong file extensions, recommended unnecessary custom agents). The codebase exploration agent reading actual source files produced a more accurate result.

**Historical data (11 queries, 3 escalations):**
- 2/3 escalations were niche/domain topics where research would have helped (Claude Code config, nightclub scenario realism)
- 1/3 was a genuine opinion split (VenueIntel UX strategy) where research would have been harmless but unhelpful
- False positive rate: ~33% — acceptable given the cost of a false positive is ~2s + one web search

**Root cause:** Multi-model consensus assumes models have independent knowledge. On niche topics, they share the same training gap — so consensus = correlated error, not wisdom of crowds.

## Landscape

- **Claude's "deep research"** — runs web searches, reads docs, synthesizes. Heavy-weight, minutes-long.
- **Perplexity/SearchGPT** — search-augmented LLMs. Fast but single-model.
- **RAG pipelines** — pre-indexed docs. Precise but requires setup per domain.
- **MOA today** — no search capability. Relies entirely on model training data.

The gap: MOA has no mechanism to fetch external knowledge when models lack it.

## Hypothesis

**If we add web search when models disagree, injecting search results as context before re-asking, then MOA will produce factually grounded responses on niche topics instead of amplifying guesses.**

Two modes:
1. **Lite search (automatic):** Triggered by low Jaccard agreement. Single web search → 2-3 results → inject → re-ask with lite proposers. Fast (~3s overhead), cheap, invisible to user.
2. **Deep research (manual, `--research deep`):** User opts in. Multi-hop search (search → read → identify gaps → search again, 2-3 rounds) → synthesize docs → single well-prompted model with full context. Thorough (~30-60s), higher quality, for questions you know need grounding.

## Design Decisions (from brainstorm + devil's advocate)

1. **Don't try to predict "niche" upfront.** The user can't tell, the classifier can't tell. Use model disagreement as the signal — it's already computed.
2. **Always research on low agreement (Option C).** No complex classifier to distinguish "guessing" from "genuine opinion split." Historical data shows 2/3 of escalations benefit from research, 1/3 are harmless false positives. Adding context never hurts, web search is cheap, latency hit only on disagreement path.
3. **Provider-agnostic search interface.** Abstract behind a `SearchProvider` protocol: `search(query) → list[SearchResult]` and `extract(url) → str`. Firecrawl is the first implementation. Swap to Tavily, Serper, or raw Google later without changing the engine. *(Devil's advocate: single dependency risk)*
4. **Search query derivation uses a model call, not string manipulation.** Use Haiku/Flash (~$0.001, ~1s) to derive 2-3 focused search queries from the original question. This is the load-bearing joint — bad queries → bad results → bad answers. Perplexity and Claude deep research both use this pattern. *(Devil's advocate: "derive search query" was hand-waved)*
5. **Research replaces blind escalation, not adds to it.** Lite search: the flow is lite → low agreement → search → re-ask with context → synthesize. Not: lite → search → escalate to ultra. Research is the remedy, not a precursor to spending more.
6. **Deep research is opt-in, not automatic.** Too slow for the default path. User triggers with `--research deep` when they know a question needs thorough grounding. Uses a single well-prompted model (not ensemble) since the value comes from the research, not model diversity.
7. **Two modes, one integration.** Both modes use the search provider interface and share the context injection mechanism. Lite = 1 search round, ensemble re-ask. Deep = 2-3 search rounds with follow-up reads, single-model synthesis.
8. **Inject as "reference context," not "ground truth."** Prompt models: "The following reference material may be relevant. Use it if applicable, but reason independently." Prevents over-anchoring on SEO-optimized blog posts. *(Devil's advocate: anchoring risk)*
9. **Deep research shows progress indicators.** "Searching... Reading 3 sources... Synthesizing..." — user opted in and is waiting, so show what's happening. Always include source citations. *(Devil's advocate: reliability expectations)*

## Proposed Flows

### Lite Search (automatic on disagreement)
```
1. Lite pass (existing — cheap, fast)
2. Evaluate agreement (existing — Jaccard similarity)
3a. High agreement (>35%) → synthesize → done (unchanged)
3b. Low agreement (<35%) → research-augmented re-ask:
    i.   Haiku/Flash derives 2-3 search queries from original question (~$0.001)
    ii.  SearchProvider.search() → 2-3 results, extract clean markdown (~4K chars)
    iii. Re-run lite proposers with "[REFERENCE CONTEXT]" prepended
    iv.  Synthesize with source attribution
    v.   If search fails → fall back to current disagreement synthesis (unchanged)
```

### Deep Research (manual: `moa ask --research deep "query"`)
```
1. Haiku/Flash derives 3-5 search queries from original question
2. Round 1: SearchProvider.search() → top 3-5 results → extract full pages
3. Haiku identifies gaps: what's still unclear or missing?
4. Round 2-3: Follow-up searches targeting gaps → extract
5. Compile research context (~8-12K chars)
6. Single well-prompted model (Opus or GPT-5.4) with full context → answer
7. Include source citations in response
8. Show progress indicators throughout
```

### Integration Point in engine.py
The research step inserts at `engine.py:541` — the `else` branch of `if agreement["consensus"]`. Currently this goes straight to `DISAGREEMENT_SYNTHESIS_PROMPT`. New flow: search → re-run proposers with context → then synthesize.

## Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Niche topic accuracy | Low (wrong specifics) | Factually grounded (correct specifics) |
| Lite search escalation cost | $0.25 (ultra) | ~$0.06-0.10 (lite + search + lite re-ask) |
| Lite search latency | ~15s (ultra models) | ~10-15s (search + lite re-ask) |
| Deep research cost | N/A (didn't exist) | ~$0.15-0.30 (search + single frontier model) |
| Deep research latency | N/A | ~30-60s (multi-hop search + synthesis) |
| False positive rate (lite) | N/A | ~33% (based on history) — acceptable, no quality degradation |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Firecrawl downtime / API changes | Medium | Provider-agnostic `SearchProvider` interface; fallback to current path |
| Search results are low quality / irrelevant | Medium | Model-derived queries (not naive); cap at 4K chars; "reference" framing lets models ignore |
| Search query derivation produces bad queries | High | Dedicated model call (Haiku/Flash) with examples; test against historical queries |
| Over-anchoring on search results | Medium | "Reference context" prompt framing; models told to reason independently |
| Adds latency to disagreement path | Low | Search ~2-3s + query derivation ~1s. Total comparable to ultra pass |
| Deep research fails loudly | Medium | Progress indicators set expectations; source citations enable verification |
| Single data point motivation | Low | Historical data shows 2/3 escalations would benefit; monitor and adjust threshold |

## Scope

**In scope:**
- `SearchProvider` protocol + Firecrawl implementation
- Search query derivation (Haiku/Flash model call)
- Lite search: auto-trigger on disagreement → search → re-ask with context
- Deep research: `--research deep` flag → multi-hop search → single-model synthesis
- Context injection with "reference" framing
- Fallback to current behavior if search fails
- Cost tracking for search + derivation steps
- Source citations in output
- Progress indicators for deep research
- `--no-research` flag to disable (for benchmarking / preference)

**Out of scope (for now):**
- Pre-indexed RAG / vector search
- Caching search results across queries
- Distinguishing factual vs opinion disagreement (Option A/B from brainstorm)
- Auto-triggering deep research (always manual for v1)
- Additional search providers beyond Firecrawl (interface is ready, implementations later)

## Dependencies

- Firecrawl API key (already available via `FIRECRAWL_API_KEY`)
- No new Python packages (HTTP calls via `httpx` or stdlib `urllib`)

## Open Questions

1. Should lite search re-run the *same* proposers or use different ones? Same = controlled comparison. Different = more diversity but harder to attribute improvement.
2. Should deep research results be cached? Same niche query twice in a day shouldn't re-search.
3. What's the right context size cap? 4K for lite, 12K for deep — or should this be configurable?

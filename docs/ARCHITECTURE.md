# Architecture

Technical deep-dive into how moa-debate is organized and why.

---

## How a query flows

```
You ask a question
    ↓
Classifier determines complexity (SIMPLE/STANDARD/COMPLEX)
and domain (FACTUAL/TECHNICAL/CREATIVE/JUDGMENT/STRATEGIC)
    ↓
Routes to the right model pool (1 cheap model for simple, 3-4 frontier models for complex)
    ↓
Models answer independently in parallel
    ↓
Agreement detection with domain-specific thresholds
(factual questions need 45% agreement, strategic only 20%)
    ↓
┌─ High agreement → Synthesize best elements
└─ Low agreement → Search the web → Re-ask with docs → Synthesize
    ↓
If STRATEGIC/JUDGMENT → add "It Depends On..." + "How to De-Risk This"
    ↓
Output: Answer + Confidence + Agreement/Disagreement + Attribution + Conditionals
```

---

## 14 models, 6 providers

**Core** (need at least one): Anthropic (Opus, Sonnet, Haiku), OpenAI (GPT-5.4, GPT-4.1, 4o-mini), Google (Gemini 3.1 Pro, 2.5 Pro, Flash)

**Optional** (auto-included when keys are set): DeepSeek (V3, R1), xAI (Grok 4, 4.1-fast), Together/Meta (Llama-4-Maverick)

## 4 tiers

| Tier | Models | Aggregator | Cost | When |
|------|--------|-----------|------|------|
| flash | Gemini Flash | none | ~$0.001 | Factoids, lookups |
| lite | 4o-mini, Flash | Sonnet | ~$0.05 | Standard questions |
| pro | GPT-4.1, Gemini Pro, Haiku | Sonnet | ~$0.09 | Reasoning, analysis |
| ultra | GPT-5.4, Gemini 3.1, Sonnet | Opus | ~$0.25 | High-stakes decisions |

---

## Module map

```
src/moa/
├── cli.py           # Typer CLI (13 commands)
├── engine.py        # Re-export layer (backward compat)
├── orchestrator.py  # Model calls, cost tracking, agreement, ranking
├── adaptive.py      # Adaptive routing, MoA, cascade, deep research, compare
├── debate.py        # Peer + adversarial debate (both composable pipelines)
├── review.py        # Expert panel code review
├── events.py        # Typed event system (EventType enum + DebateEvent)
├── export.py        # Shareable transcript export (HTML + markdown)
├── outcomes.py      # Outcome tracking (verdict → decision → result)
├── models.py        # 14 models, 4 tiers, 14 personas, reviewer roles
├── templates.py     # Decision templates (built-in + custom YAML)
├── health.py        # Circuit breakers, health-aware model selection
├── research.py      # SearchProvider protocol, Firecrawl + DuckDuckGo
├── prompts.py       # All prompt templates
├── server.py        # FastAPI HTTP API (5 endpoints)
├── context.py       # Project context detection + injection
├── config.py        # Constants (timeouts, budget, rate limits)
├── cache.py         # SQLite response caching (1hr TTL)
├── budget.py        # Daily spend cap ($5/day default)
├── history.py       # JSONL query logging
└── verify.py        # Model connectivity test

templates/examples/  # 6 shippable decision templates (install via CLI)
hooks/               # Tracked git hooks (./hooks/install.sh)
tests/
├── quality_checks.py        # Reusable assertions: structural / invariants / LLM-judge rubric
├── test_e2e.py              # 4-tier e2e: T1 free / T2 ~$0.004 / T3 ~$0.60 / T3.5 ~$0.10
└── test_*.py                # 197 mock tests across 10 files
```

---

## Composable debate pipelines

Both peer and adversarial debates use the same pipeline pattern:

```python
state = DebateState(query=..., ...)
for stage in PIPELINE:
    state = await stage(state)
return format_result(state)
```

**Peer pipeline stages**:
```
peer_select_models → peer_independent → peer_challenge →
peer_revision_rounds → peer_judge
```

**Adversarial pipeline stages**:
```
resolve_template → select_models → research →
opening → rounds → judge
```

Each stage is `async def stage(state) -> state`. You can swap, reorder, or skip stages by passing a custom `pipeline=[...]` argument to `run_peer_pipeline()` or `run_adversarial_pipeline()`. Both emit typed `DebateEvent` objects (see `events.py`) that the CLI subscribes to for progress display.

---

## Adaptive routing

Every query is classified by complexity and domain. Simple factual questions hit 1-2 cheap models. Complex strategic questions use 3-4 frontier models with synthesis. You never configure this — it just works.

### Domain-aware responses

Every query is classified into a domain. This affects two things: (1) how much model agreement is needed before triggering research, and (2) whether the response includes conditional analysis and de-risking steps.

| Domain | Agreement Threshold | Extra Output |
|--------|-----------|-----|
| FACTUAL | 45% | Standard answer |
| TECHNICAL | 40% | Standard answer |
| CREATIVE | 30% | Standard answer |
| JUDGMENT | 25% | + "It Depends On..." + "How to De-Risk This" |
| STRATEGIC | 20% | + "It Depends On..." + "How to De-Risk This" |

For STRATEGIC and JUDGMENT queries, the synthesizer automatically adds:
- **It Depends On...** — conditional scenarios where the answer changes
- **How to De-Risk This** — 3-5 specific steps you can do in days, not months

---

## Research-augmented routing

When models disagree, the system:
1. Uses a cheap model to derive 2-3 search queries
2. Searches the web via [Firecrawl](https://firecrawl.dev) (falls back to DuckDuckGo if no Firecrawl key — free, no API key needed)
3. Re-asks the same models with reference docs injected
4. Synthesizes with source attribution

This prevents the biggest failure mode of multi-model consensus: **correlated hallucination**. When all models share the same training gap (e.g., niche tooling), they confidently guess different wrong answers. Research grounds them in reality.

Force deep research: `moa ask --research deep "query"` runs 2-3 rounds of web search, identifies gaps, and synthesizes with a single frontier model.

---

## Pairwise ranking

Instead of picking the longest response (a common but terrible heuristic), a cheap model compares responses pairwise to select the genuinely best one. The footer shows `👑 Best: model-name`. Inspired by [LLM-Blender](https://github.com/yuchenlin/LLM-Blender).

---

## Trust signals

Every response includes transparency features:
- **Confidence bar** (██████░░░░) with HIGH/MODERATE/MIXED/LOW label
- **Correlated confidence warning** — alerts you when high agreement on a niche topic might be shared hallucination
- **Factual verification** — on factual queries, checks for suspicious precision and conflicting numbers
- **Session memory** — tracks previous answers to flag contradictions within a session

---

## Design decisions

### Why multiple providers, not multiple models from one provider?
Models from the same provider share training data and biases. GPT-4.1 and GPT-5.4 will often make the same mistakes. True diversity requires different companies, different training pipelines, different architectural decisions.

### Why domain-capped thresholds instead of a flat agreement score?
A flat 35% threshold triggers research too aggressively on opinion questions (where disagreement is expected) and not aggressively enough on factual questions (where disagreement means someone's hallucinating).

### Why a challenge round before debate revision?
Without it, models tend to converge on the first answer that sounds reasonable (sycophantic agreement). Forcing them to find flaws first produces genuinely stronger arguments. Inspired by [duh](https://github.com/msitarzewski/duh).

### Why pairwise ranking instead of just picking the longest response?
Longer isn't better. A concise, correct answer should beat a verbose, hedging one. Pairwise comparison with a cheap model (~$0.003) catches this.

### Why research on disagreement instead of on every query?
Most queries don't need web search — the models know the answer. Search adds 3-5 seconds of latency and costs Firecrawl credits. By only triggering on disagreement, you get the benefit when it matters and skip the overhead when it doesn't.

### Why personas instead of just "review this code"?
Different reviewers catch different things. A security specialist finds injection vulnerabilities. Sandi Metz finds classes with too many responsibilities. Rich Hickey finds unnecessary complexity. Generic "review this" misses the specific angles that matter.

### Why composable pipelines for both debate styles?
Once peer and adversarial fit the same `state → stages → format_result` shape, they become interchangeable: you can swap stages, replace one, A/B test variants. Adding a third debate style (tournament bracket, devil's-advocate-only) becomes a stage definition, not a new function.

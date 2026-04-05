# Session Handoff — 2026-04-05 (Session 3)

**Date:** 2026-04-05
**Project:** moa-debate
**Commits:** 42 (6 new this session)
**Branch:** main

## What We Built This Session

### Features
- **Research-grounded debates** — both sides get web sources before arguing, cite evidence, judge verifies claims
- **DuckDuckGo search fallback** — research works without Firecrawl key (free, no API needed)
- **Circuit breakers** (`health.py`) — tracks model failures, auto-skips broken models, half-open recovery after 10 min
- **Decision templates** (`templates.py`) — `--template hire|build|invest` with domain-specific judge criteria
- **Animated fight scenes** — stick figure sword fight + spinner during model calls
- **Structured verdicts** — TL;DR, confidence/10, decision tree, evidence quality, "what both sides got wrong"
- **Debate transcripts** — full arguments saved to `~/.moa/debates/` as markdown
- **`moa health`** — show model circuit breaker states
- **`moa templates`** — list available decision templates

### Fixes
- GPT-5.4 timeout: was 45s, debate prompts take 25-45s. Increased to 90s for debates.
- `available` → `ranked` NameError in adversarial fallback
- urllib3 NotOpenSSLWarning suppressed at package init
- Battle card emoji alignment (proper Unicode display width math)

### Prompt Improvements
- Aggregator: explicit conflict resolution rules (facts vs reasoning vs subjective)
- Debate rounds: anti-sycophancy (hold position if reasoning is sound)
- Search queries: source hierarchy (specs > docs > blogs)
- Fact-checker: compound risk detection, cross-model inconsistency signal
- Angel/devil: "lead with argument, not meta-commentary" + cite sources
- Judge: TL;DR, confidence score, decision tree, evidence quality, assumptions that would flip verdict

### Research-Backed Design Decision
Templates modify judge heavily but angel/devil only get light context. Based on:
- Bandi et al. (2024): constraining advocates causes argument collapse
- Schmidt & Hunter (1998): structured evaluation (judge) > structured argumentation (debaters)

## Architecture — What Needs Refactoring

From moa's own self-review debates:

### Priority 1: Split engine.py (1700+ lines)
```
engine.py → orchestrator.py  (call_model, agreement, cost tracking)
          → debate.py        (peer + adversarial debate)
          → review.py        (expert panel)
          → adaptive.py      (routing + cascade)
```

### Priority 2: Debate as pipeline, not monolith
`_run_adversarial_debate` is 400+ lines. Should be composable stages:
```
research → select_models → opening → rounds → judge → format
```
Each stage testable independently.

### Priority 3: Structured intermediate output
Currently parsing free-text to extract theses and agreement scores. Should use JSON mode for intermediate rounds, free text only for final verdict.

### Priority 4: Progress as typed events
Replace `_progress("__FIGHT_START__")` string signals with typed events:
```python
DebateEvent(type=EventType.ROUND_START, round=2, models=[...])
```
CLI subscribes to event stream.

## Current State

**Tests:** 26 unit tests passing
**Models:** 14 models, 6 providers. GPT-5.4 works with 90s timeout. Gemini 2.5 Flash/Pro failing (NoneType error in LiteLLM).
**Health file:** `~/.moa/health.json` tracks circuit breaker state
**Debates dir:** `~/.moa/debates/` stores full transcripts

## Remaining Work (Updated)

### Done This Session
- [x] Suppress urllib3 NotOpenSSLWarning
- [x] Provider health tracking (circuit breakers)
- [x] Research-grounded debates
- [x] DuckDuckGo search fallback
- [x] Decision templates (hire, build, invest)
- [x] Animated debate UX
- [x] Structured verdicts
- [x] Debate transcripts

### Still TODO
- [ ] Engine decomposition (Priority 1 refactor above)
- [ ] `moa compare` — single model vs ensemble side-by-side
- [ ] Custom user templates in `~/.moa/templates/`
- [ ] More templates: startup, launch, strategy
- [ ] Outcome tracking — log verdicts, record what actually happened
- [ ] Cache deep research results
- [ ] Rewrite README for new features
- [ ] Update CLAUDE.md with new modules (health.py, templates.py)
- [ ] Record demo with asciinema
- [ ] Rotate API keys

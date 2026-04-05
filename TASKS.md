# TASKS — moa-debate

## Next Session: Engine Refactor

### Priority 1: Split engine.py
- [ ] Extract `orchestrator.py` — call_model, compute_agreement, cost tracking, shared utils
- [ ] Extract `debate.py` — run_debate, _run_adversarial_debate, _run_peer_debate
- [ ] Extract `review.py` — run_expert_review, reviewer discourse
- [ ] Extract `adaptive.py` — run_adaptive, run_cascade, run_deep_research
- [ ] Update all imports in cli.py, server.py, tests
- [ ] Verify 26 tests still pass after extraction

### Priority 2: Debate as pipeline
- [ ] Define stage protocol: `async def stage(context: DebateContext) -> DebateContext`
- [ ] Extract: research_stage, model_selection_stage, opening_stage, round_stage, judge_stage
- [ ] Each stage independently testable
- [ ] Add unit tests for individual stages

### Priority 3: Typed event system
- [ ] Define `DebateEvent` dataclass with `EventType` enum
- [ ] Replace `_progress("__FIGHT_START__")` string signals
- [ ] CLI subscribes to typed events
- [ ] Clean separation between engine logic and presentation

### Priority 4: Structured intermediate output
- [ ] Use JSON mode for round summaries (thesis extraction, agreement)
- [ ] Free text only for final verdict
- [ ] Better `_best_sentence` extraction from structured data

## Features Backlog

### Templates
- [ ] Add startup template (burn rate, validation evidence, market timing)
- [ ] Add launch template (market timing, tech debt, user trust)
- [ ] Add strategy template (unit economics, competitive moats, reversibility)
- [ ] Custom user templates from `~/.moa/templates/*.yaml`
- [ ] Template auto-suggest: "Did you mean to use the 'hire' template?"

### Product
- [ ] `moa compare` — single model vs ensemble side-by-side
- [ ] Outcome tracking — log verdicts + record what happened → learn which combos work
- [ ] Workflow hooks — pipe verdicts to clipboard, Slack, Notion
- [ ] Cache deep research results (same query shouldn't re-search)

### Documentation
- [ ] Rewrite README for new features (templates, research, circuit breakers)
- [ ] Update CLAUDE.md with health.py, templates.py modules
- [ ] Add ARCHITECTURE.md
- [ ] Record demo with asciinema (script at docs/marketing/demo-script.md)

### Quality of Life
- [ ] `--quiet` flag to suppress confidence panel (for piping)
- [ ] Fix Gemini 2.5 Flash/Pro NoneType errors
- [ ] Rotate API keys (exposed during previous session)

## Completed (2026-04-05, Session 3)

- [x] Research-grounded debates (Firecrawl + DuckDuckGo fallback)
- [x] Circuit breakers (`health.py`) — auto-skip failing models
- [x] GPT-5.4 timeout fix (45s → 90s for debates)
- [x] Health-aware model selection for debates
- [x] Decision templates: hire, build, invest (`templates.py`)
- [x] Template auto-detection from query keywords
- [x] `moa health` command
- [x] `moa templates` command
- [x] Animated fight scenes + spinner
- [x] Structured verdicts (TL;DR, confidence, decision tree, evidence quality)
- [x] Debate transcripts to `~/.moa/debates/`
- [x] Optimized prompts (anti-sycophancy, conflict resolution, source hierarchy)
- [x] urllib3 warning suppression
- [x] Battle card dynamic sizing with Unicode display width
- [x] `_best_sentence` extraction (specificity scoring, skip preamble)
- [x] `available` → `ranked` NameError fix

## Completed (2026-04-04, Sessions 1-2)

- [x] Research-augmented routing (Firecrawl)
- [x] 8 competitor-inspired features
- [x] 14 personas, 5 categories
- [x] Rich output (confidence bars, attribution)
- [x] Trust signals (correlated confidence, factual verification)
- [x] Strategic intelligence (conditionals, de-risking)
- [x] Live debate UX (battle card, previews, timer)
- [x] `moa test` command, validation suite
- [x] Public repo, README, docs

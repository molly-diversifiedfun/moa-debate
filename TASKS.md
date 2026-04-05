# TASKS — moa-debate

## Remaining Work

### Documentation Improvements
- [ ] Rewrite README intro: why we built this, who it's for, design philosophy, how context/prompts work
- [ ] Add ARCHITECTURE.md: how the engine works, prompt design choices, model selection rationale
- [ ] Add CONTRIBUTING.md if open-sourcing for community

### Rich Output Phase B (deferred)
- [ ] Engine-driven extraction of agreement/disagreement points (currently prompt-driven)
- [ ] More reliable structured output than relying on synthesizer formatting
- [ ] Parse response sections programmatically for rendering

### Validation Suite Gaps
- [ ] Run remaining validation tests: 3 (research), 9 (discourse), 10 (multi-layer), 14-17 (MOA-designed)
- [ ] Add research test to `moa test` command (needs Firecrawl key check)
- [ ] Add discourse test to `moa test --full`

### Quality of Life
- [ ] Suppress urllib3 NotOpenSSLWarning (upgrade Python 3.9 → 3.11+, or filter)
- [ ] Cache deep research results (same niche query twice shouldn't re-search)
- [ ] Add `--quiet` flag to suppress confidence panel (for piping)
- [ ] Disable Vercel plugin hooks for this project (Python CLI, not Vercel)

### Future Features
- [ ] `moa compare` — run same query on single model vs ensemble, show side-by-side
- [ ] Learned router (replace classifier with a fine-tuned model based on history.jsonl)
- [ ] Provider health tracking (auto-skip providers with recent failures)
- [ ] Web UI for non-CLI users (FastAPI already exists as server)

## Completed (2026-04-04)

### Research-Augmented Routing
- [x] Firecrawl integration (SearchProvider protocol + FirecrawlProvider)
- [x] Lite search (auto on disagreement) + deep research (manual --research deep)
- [x] Search query derivation via cheap model
- [x] Firecrawl v2 API fix (was silently failing)

### 8 Competitor-Inspired Improvements
- [x] #1 Domain-capped confidence (from duh)
- [x] #2 Forced challenge round (from duh)
- [x] #3 Convergence early exit (from duh)
- [x] #4 Multi-layer MoA (from togethercomputer/MoA)
- [x] #5 Reviewer discourse (from Open Code Review)
- [x] #6 Famous engineer personas (from Open Code Review)
- [x] #7 Angel/devil/judge debate (from Multi-Agents-Debate)
- [x] #8 Pairwise ranking (from LLM-Blender)

### Universal Persona System
- [x] 14 personas across 5 categories (code, architecture, product, content, builder)
- [x] Works on ask, debate, and review commands
- [x] Selectable by name or category with fuzzy matching

### Rich Output Format (Phase A)
- [x] Structured synthesizer prompts (Answer, Agreement, Disagreement, Attribution)
- [x] Confidence bar + domain classification in CLI
- [x] Model attribution + pairwise ranking winner in footer

### Trust Signals
- [x] Correlated confidence warning
- [x] Factual verification (checks for suspicious precision)
- [x] Session memory (logs + consistency injection)

### Infrastructure
- [x] Claude Code project setup (CLAUDE.md, rules, settings.json)
- [x] Session-retrospective hook fix (infinite loop on read-only sessions)
- [x] LiteLLM + SSL noise suppression
- [x] Domain classifier improvement (examples + disambiguation)
- [x] Adversarial debate fallback on model failure
- [x] `moa test` command (5 smoke tests, all passing)
- [x] Repo made public
- [x] README, USE_CASES.md, CLAUDE.md, slash commands all updated
- [x] Validation suite (17 tests + scoring rubric)

# TASKS — moa-debate

## Ready to Build

### Competitor-Inspired Improvements (8 features, 4 phases)
**Spec:** `.specs/tasks/todo/competitor-improvements.feature.md`
**Status:** Spec complete, ready for `/build`

**Phase 1: Debate Upgrades** (~70 lines, trivial)
- [ ] #2 Forced Challenge Round — challenge prompt + round insertion before revision
- [ ] #3 Convergence Early Exit — compute_agreement() between rounds, exit if >0.7
- [ ] #7 Angel/Devil/Judge — adversarial debate style with `--style` flag

**Phase 2: Smarter Agreement** (~80 lines, medium)
- [ ] #1 Domain-Capped Confidence — extend classifier to output domain, apply per-domain thresholds
- [ ] #8 Pairwise Ranking — Haiku/Flash pairwise comparison, supplement Jaccard

**Phase 3: Code Review Upgrades** (~60 lines, medium)
- [ ] #5 Reviewer Discourse — AGREE/CHALLENGE/CONNECT/SURFACE round with `--discourse` flag
- [ ] #6 Famous Engineer Personas — Fowler/Beck/Hickey/Metz with `--personas` flag

**Phase 4: Multi-Layer MoA** (~30 lines, medium)
- [ ] #4 Multi-Layer Aggregation — re-run proposers on synthesis with `--layers` flag

## Completed

### Research-Augmented Routing (2026-04-04)
- [x] Add `firecrawl-py` dependency to pyproject.toml
- [x] Create `src/moa/research.py` (SearchProvider, FirecrawlProvider, lite_search, deep_research)
- [x] Add prompt templates to `src/moa/prompts.py`
- [x] Modify `engine.py` disagreement branch for lite search
- [x] Add `run_deep_research()` to engine.py
- [x] Add `--research` flag to CLI
- [x] Update config.py + .env.example
- [x] Write tests (tests/test_research.py) — 10 tests, all passing
- [x] Update CLAUDE.md

### Session-Retrospective Hook Fix (2026-04-04)
- [x] Fix infinite loop in `~/.claude/hooks/session-retrospective.sh` — added git commit check so enforcement requirement only fires when commits were made today

### Claude Code Project Setup (2026-04-04)
- [x] Expand CLAUDE.md (33 → 97 lines)
- [x] Create `.claude/rules/model-safety.md`
- [x] Create `.claude/rules/architecture.md`
- [x] Create `.claude/settings.json` (wire moa-review.sh hook)

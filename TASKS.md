# TASKS — moa-debate

## In Progress

### Research-Augmented Routing
**Spec:** `.specs/tasks/todo/research-augmented-routing.feature.md`
**Brief:** `docs/briefs/research-augmented-routing-brief.md`
**Status:** Spec complete, ready for `/build`

Tasks:
- [ ] Add `firecrawl-py` dependency to pyproject.toml
- [ ] Create `src/moa/research.py` (SearchProvider, FirecrawlProvider, lite_search, deep_research)
- [ ] Add prompt templates to `src/moa/prompts.py`
- [ ] Modify `engine.py` disagreement branch for lite search
- [ ] Add `run_deep_research()` to engine.py
- [ ] Add `--research` flag to CLI
- [ ] Update config.py + .env.example
- [ ] Write tests (tests/test_research.py)
- [ ] Update CLAUDE.md

## Completed

### Session-Retrospective Hook Fix (2026-04-04)
- [x] Fix infinite loop in `~/.claude/hooks/session-retrospective.sh` — added git commit check so enforcement requirement only fires when commits were made today

### Claude Code Project Setup (2026-04-04)
- [x] Expand CLAUDE.md (33 → 97 lines)
- [x] Create `.claude/rules/model-safety.md`
- [x] Create `.claude/rules/architecture.md`
- [x] Create `.claude/settings.json` (wire moa-review.sh hook)

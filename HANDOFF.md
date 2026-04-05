# Session Handoff — 2026-04-04

**Date:** 2026-04-04
**Project:** moa-debate

## Current State

**Task:** Major feature build session — 18 commits, repo made public
**Phase:** Implementation complete, validation in progress
**Progress:** ~90% — all features shipped, partial validation done

## What We Did This Session

Massive build session. Fixed the session-retrospective hook, set up Claude Code project config, then built 12 major features:

1. **Research-augmented routing** — Firecrawl web search on model disagreement + deep research mode
2. **Debate: challenge round** — forced disagreement before revision (from duh)
3. **Debate: convergence exit** — early stop when agreement >70% (from duh)
4. **Debate: adversarial mode** — angel/devil/judge pattern (from Multi-Agents-Debate)
5. **Domain-capped confidence** — per-domain agreement thresholds (from duh)
6. **Pairwise ranking** — cheap model compares response pairs (from LLM-Blender)
7. **Reviewer discourse** — AGREE/CHALLENGE/CONNECT/SURFACE round (from Open Code Review)
8. **Famous personas (code)** — Fowler/Beck/Hickey/Metz review mode (from Open Code Review)
9. **Multi-layer MoA** — verification pass with --layers flag (from togethercomputer/MoA)
10. **Universal persona system** — 14 personas across 5 categories, works on ask/debate/review
11. **Rich output format** — confidence bars, attribution, structured sections
12. **Trust signals** — correlated confidence warning, factual verification, session memory

Also: made repo public, rewrote README and USE_CASES.md, updated all 3 slash commands.

## Commits This Session (18)

All on main, all pushed.

## Decisions Made

- **Approach B for research** — new research.py module with SearchProvider protocol, not inline in engine.py
- **firecrawl-py SDK** — not raw HTTP, not MCP (MCP only available to Claude Code, not standalone CLI)
- **Option C for research trigger** — always search on low agreement, don't try to distinguish guessing from opinion splits
- **Prompt-driven rich output (Phase A)** — tell synthesizer to output structured sections, not engine-driven extraction (Phase B deferred)
- **14 personas, 5 categories** — code, architecture, product, content, builder
- **Session memory logs but doesn't yet block** — consistency checking is advisory, not enforced

## Known Issues

- **Domain classifier** — improved with examples but may still misclassify edge cases
- **Python 3.9 SSL errors** — suppressed via atexit handler. Would go away with Python 3.11+
- **urllib3 NotOpenSSLWarning** — cosmetic, from system Python's LibreSSL

## Validation Results (partial)

| Test | Result |
|------|--------|
| 1: Multi-model value | PASS |
| 2a: Factual confidence | PASS |
| 2b: Strategic threshold | PASS (after classifier fix) |
| 6: Adversarial debate | PASS |
| 7c: Sandi Metz persona | PASS |
| 8b: Builder personas | PASS |

Not yet run: tests 3, 5, 9, 10, 14-17.

## Next Steps

1. [ ] Run remaining validation tests (3, 5, 9, 10, 14-17)
2. [ ] Build `moa test` command — automated smoke test runner
3. [ ] Rich output Phase B — engine-driven agreement/disagreement extraction
4. [ ] Update project_overview.md memory (outdated)
5. [ ] Consider disabling Vercel plugin hooks for this project

## Files to Review on Resume

- `src/moa/engine.py` — core orchestration, all flows
- `src/moa/models.py` — persona registry, reviewer roles
- `src/moa/research.py` — search provider + research flows
- `tests/VALIDATION.md` — 17 live validation tests

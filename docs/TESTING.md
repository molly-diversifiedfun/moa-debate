# Testing

Test infrastructure, quality checks, and git hooks for moa-debate.

---

## Quick reference

```bash
pytest                     # 197 mock tests, ~7s, free
moa verify                 # Ping all models (cheap)
moa test                   # 5 live smoke tests (~$0.50)
moa test --full            # 8 extended tests (~$1)
./hooks/install.sh         # Install git hooks (one-time, after clone)
```

---

## 4-tier e2e framework

`tests/test_e2e.py` is gated by environment variables so CI runs free and live runs are explicit.

| Tier | Tests | Cost | Time | Gate | Catches |
|------|-------|------|------|------|---------|
| **T1** | 17 | free | ~3s | always runs | Typer wiring, error paths, file I/O, help output |
| **T2** | 4 | ~$0.004 | ~10s | `MOA_E2E_LIVE=1` | Live single-model calls, model identifier drift |
| **T3** | 6 | ~$0.60 | ~8min | `MOA_E2E_EXPENSIVE=1` | Full debate/compare/export end-to-end |
| **T3.5** | 2 | ~$0.10 | ~3min | `MOA_E2E_RUBRIC=1` | Semantic quality via LLM-as-judge |
| **T4** | 1 | ~$0.50 | ~3min | `MOA_E2E_EXPENSIVE=1` | `moa test` command smoke |

### Run commands

```bash
# T1 only — free, always safe
pytest tests/test_e2e.py

# T1 + T2 — cheap live validation (~$0.004)
MOA_E2E_LIVE=1 pytest tests/test_e2e.py

# T1 + T3 — full live validation (~$0.60)
MOA_E2E_EXPENSIVE=1 MOA_E2E_LIVE=1 pytest tests/test_e2e.py

# Everything including rubric (~$0.70 total)
MOA_E2E_RUBRIC=1 MOA_E2E_EXPENSIVE=1 MOA_E2E_LIVE=1 pytest tests/test_e2e.py
```

**Recommended cadence**: T1 on every commit (via hooks). T2 a few times a week during active development. T3/T3.5 before releases.

---

## Quality checks library

`tests/quality_checks.py` provides reusable assertions across three layers. Import and wire them into any live test.

### Layer 1 — Structural (free, deterministic)
- Required judge sections present (`TL;DR`, `Confidence`, `Case For`, `Case Against`, `Decision Tree`, `Bottom Line`)
- Decision tree ASCII chars present (`├──`, `└──`), max 3 levels deep
- Confidence score extractable and in `[1, 10]`
- Both advocate and critic mentioned in verdict
- Query vocabulary overlap ≥15% (catches generic-preamble failures)
- Word count in sane range `[150, 5000]`

### Layer 2 — Pipeline invariants (free)
- Cost > 0 and ≤ per-tier ceiling (catches "all calls failed silently" bugs)
- Rounds actually evolved (Jaccard delta ≥15% between first and last round)
- ≥2 models succeeded
- Adversarial angel ≠ devil (provider diversity)

### Layer 3 — LLM-as-judge rubric (~$0.002 per call)
A cheap judge (Gemini Flash or Haiku) scores the verdict 1-5 on:
- `answers_question` — directly addresses the original query
- `considers_tradeoffs` — weighs both sides with judgment
- `actionable` — concrete next steps, not just analysis
- `specific_not_vague` — numbers, examples, thresholds (not platitudes)

Fails if any dimension <3. ~5% flaky (LLM noise), so a single failure is not conclusive.

### Usage

```python
from tests.quality_checks import (
    assert_adversarial_quality,
    assert_peer_quality,
    score_verdict_with_rubric,
    assert_rubric_scores_pass,
)

# Layer 1 + 2 together
result = await run_adversarial_pipeline(query, ...)
confidence = assert_adversarial_quality(result, original_query=query, tier="lite")

# Layer 3
scores = await score_verdict_with_rubric(query, result["response"])
assert_rubric_scores_pass(scores, min_score=3)
```

---

## Git hooks (recommended)

Install once after cloning:

```bash
./hooks/install.sh
```

This symlinks two hooks into `.git/hooks/`. Because they're symlinks, editing `hooks/pre-*` immediately updates the active hooks — no reinstall needed.

### What each hook does

| Hook | Trigger | Check | Time |
|---|---|---|---|
| **pre-commit** | `git commit` | If `src/moa/cli.py` is staged, runs `python3 -c "from moa.cli import app"` | ~1s |
| **pre-push** | `git push` | Runs the full `pytest -q` mock suite | ~7s |

### What they catch

- **pre-commit**: missing imports, syntax errors, name shadowing, `UnboundLocalError` in CLI code. Real bugs caught in the wild: Session 4's missing `Optional` import that broke every CLI command, Session 5's local `from pathlib import Path` that shadowed the module-level import.
- **pre-push**: any regression in the 197 mock tests. Fast enough to not be annoying, complete enough to catch real breakage.

### Bypass (when you really need it)

```bash
git commit --no-verify
git push --no-verify
```

Use sparingly — these checks exist because we've already shipped the bugs they catch.

---

## Test file inventory

```
tests/
├── quality_checks.py          # Reusable assertion library (not run directly)
├── test_e2e.py                # 30 tests across 4 tiers
├── test_engine.py             # 16 tests — core engine, cost tracking
├── test_research.py           # 10 tests — web search grounding
├── test_templates.py          # 17 tests — built-in + custom YAML templates
├── test_example_templates.py  # 34 tests — shipped example templates validate
├── test_debate_pipeline.py    # 19 tests — adversarial pipeline stages
├── test_peer_pipeline.py      # 13 tests — peer pipeline stages
├── test_events.py             # 27 tests — typed event system
├── test_export.py             # 23 tests — HTML + markdown transcript export
├── test_outcomes.py           # 17 tests — outcome tracking feedback loop
└── test_compare.py            # 6 tests — moa compare command
```

Total: 197 mock tests + 14 live tests (T2+T3+T3.5) = 211 tests available.

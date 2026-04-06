# Superior Features Spec — moa-debate

**Date:** 2026-04-05
**Status:** Draft — review before building

---

## Feature 1: Outcome Tracking

**The pitch:** Debates produce verdicts that vanish. Outcome tracking closes the loop — log what you decided, tag what actually happened, and over time see how well the ensemble predicts reality.

### Data Model

```
~/.moa/outcomes.jsonl   # append-only log
```

Each entry:
```json
{
  "id": "debate-2026-04-05-abc123",
  "ts": "2026-04-05T14:30:00",
  "query": "Should we hire a senior engineer?",
  "verdict": "YES — hire senior, backfill junior later",
  "confidence": 7,
  "template": "hire",
  "debate_style": "adversarial",
  "key_assumptions": ["budget exists", "pipeline is full"],
  "decision": null,
  "outcome": null,
  "outcome_ts": null,
  "tags": []
}
```

### CLI Commands

```bash
# After a debate, automatically logs verdict + assumptions
# (no new command needed — debate already saves transcripts)

# Record what you actually decided
moa outcome log <debate-id> --decision "hired senior, started Mar 15"

# Record what happened
moa outcome tag <debate-id> --outcome "great hire, shipped 3 features in Q2" --result good

# View outcomes
moa outcomes                          # list all with status
moa outcomes --pending                # debates with no outcome yet
moa outcomes --stats                  # accuracy by template, style, confidence

# Nudge: remind me to tag outcomes
moa outcomes --stale                  # >30 days old, no outcome tagged
```

### Stats Output

```
Outcome Tracking — 47 debates, 31 with outcomes

By template:
  hire:    8/10 correct (80%)  — avg confidence: 7.2
  build:   5/8 correct (63%)   — avg confidence: 6.1
  invest:  3/5 correct (60%)   — avg confidence: 5.8

By style:
  adversarial: 22/28 correct (79%)
  peer:        9/13 correct (69%)

By confidence:
  8-10: 12/13 correct (92%)  ← high confidence = high accuracy
  5-7:  14/20 correct (70%)
  1-4:  5/8 correct (63%)    ← low confidence = flip a coin

Insight: adversarial debates at confidence ≥8 have been right 95% of the time.
```

### Implementation

| File | Changes |
|------|---------|
| `outcomes.py` (new) | `log_outcome()`, `tag_outcome()`, `get_outcomes()`, `compute_stats()` |
| `cli.py` | `moa outcome log`, `moa outcome tag`, `moa outcomes` commands |
| `debate.py` | `format_result()` writes outcome entry after each debate |
| `config.py` | `OUTCOMES_FILE` path constant |

### Key Decision: Structured confidence extraction

The judge verdict is free text. To get a numeric confidence for stats, we need to either:
- **(A)** Parse it from the structured verdict (already has "confidence/10")
- **(B)** Add a second cheap model call to extract structured fields

Recommend **(A)** — the verdict format already includes confidence. Parse with regex fallback.

---

## Feature 2: Shareable Debate Transcripts

**The pitch:** Debates are saved to `~/.moa/debates/` but they're raw JSON. Export to a clean, self-contained HTML file you'd paste in a PR, Slack thread, or share with a cofounder.

### CLI Commands

```bash
# Export last debate as HTML
moa export                            # last debate → stdout
moa export --format html              # self-contained HTML file
moa export --format md                # clean markdown
moa export <debate-id>                # specific debate
moa export --output debate.html       # write to file

# Also: add --export flag to debate command itself
moa debate --style adversarial "..." --export html
```

### HTML Template

Single self-contained HTML file (inline CSS, no external deps):

```
┌──────────────────────────────────────┐
│  ⚔️ ADVERSARIAL DEBATE               │
│  "Should we build auth in-house?"    │
│  2026-04-05 • build template         │
│  Models: claude-opus vs gpt-5.4      │
├──────────────────────────────────────┤
│  📚 SOURCES (6 cited)               │
│  ▸ Auth0 pricing docs               │
│  ▸ AWS Cognito comparison...         │
├──────────────────────────────────────┤
│  ROUND 1                            │
│  👼 Advocate    │  😈 Critic         │
│  "Build gives   │  "Auth is a       │
│   you control"  │   solved problem" │
│  Agreement: ██░░ 23%                │
├──────────────────────────────────────┤
│  ROUND 2                            │
│  👼 "Concedes   │  😈 "Even with    │
│   maintenance"  │   Auth0 lock-in"  │
│  Agreement: ████ 41%                │
├──────────────────────────────────────┤
│  ⚖️ VERDICT                          │
│  Use Auth0 for now. Build custom     │
│  when you hit 10K users and need...  │
│                                      │
│  Confidence: 7/10                    │
│  Key assumption: <10K users today    │
├──────────────────────────────────────┤
│  🌳 DECISION TREE (see Feature 4)   │
│  Cost: $0.34 • Latency: 45s         │
│  3 rounds • converged at round 3    │
└──────────────────────────────────────┘
```

Collapsible rounds (click to expand full arguments). Verdict always visible.

### Implementation

| File | Changes |
|------|---------|
| `export.py` (new) | `export_html()`, `export_markdown()`, HTML template string |
| `cli.py` | `moa export` command, `--export` flag on `debate` |
| `debate.py` | No changes — already returns all data needed |

### Key Decision: Template approach

- **(A)** Jinja2 template — flexible but adds dependency
- **(B)** f-string template — zero deps, inline CSS, good enough

Recommend **(B)** — this is a single page with inline CSS. No need for a template engine. The HTML is ~200 lines of template.

---

## Feature 3: Custom YAML Templates

**The pitch:** Hardcoded `hire|build|invest` templates limit users to our decision domains. YAML templates in `~/.moa/templates/` let anyone define their own.

### Template Format

```yaml
# ~/.moa/templates/launch.yaml
name: launch
description: "Product launch timing — should we ship now or wait?"
keywords:
  - launch
  - ship
  - release
  - go live
  - ready to ship

debater_context: >
  This is a product launch timing decision. Consider market timing,
  product readiness, competitive pressure, and team capacity.

judge_addendum: >
  Evaluate using these criteria:
  1. Product readiness (bugs, missing features, UX polish)
  2. Market timing (competition, seasonal factors, press opportunities)
  3. Team capacity (can they support launch + iterate?)
  4. Reversibility (can we soft-launch and pull back?)
  
  Weight market timing heavily — a good product at the wrong time
  often loses to a decent product at the right time.

research_queries:
  - "product launch timing strategy"
  - "when to ship vs when to wait software"
  - "soft launch vs hard launch"
```

### Discovery

Templates loaded in priority order:
1. `~/.moa/templates/*.yaml` (user custom — highest priority)
2. Built-in templates in `templates.py` (fallback)

User templates with the same `name` as a built-in override it completely.

### CLI Commands

```bash
# List all templates (built-in + custom)
moa templates                         # already exists, extend it
moa templates --verbose               # show keywords + description

# Validate a template
moa templates validate ~/.moa/templates/launch.yaml

# Use custom template
moa debate --template launch "Should we ship the redesign Friday?"
```

### Auto-Detection

The existing `detect_template()` function already matches query keywords. Custom templates participate in auto-detection via their `keywords` list. If multiple templates match, longest keyword match wins.

### Implementation

| File | Changes |
|------|---------|
| `templates.py` | `load_custom_templates()`, `load_all_templates()`, YAML schema validation |
| `cli.py` | Extend `moa templates` with `--verbose`, add `validate` subcommand |
| `config.py` | `TEMPLATES_DIR` path constant |
| `pyproject.toml` | Add `pyyaml` dependency |

### Key Decision: Schema validation

- **(A)** Strict schema with jsonschema — catches errors early
- **(B)** Duck-type validation — check required keys exist, warn on unknown keys

Recommend **(B)** — keep it simple. Check that `name`, `debater_context`, `judge_addendum` exist. Warn on unknown keys. No jsonschema dependency.

---

## Feature 4: Decision Tree Output

**The pitch:** The "It Depends On..." section lists conditionals as prose. A decision tree makes them actionable — something you'd paste in a doc and actually walk through.

### Output Format

Added to the structured verdict as a new section:

```
🌳 DECISION TREE

Should we build auth in-house?
├── Do you have >10K users today?
│   ├── YES → Do you have a dedicated security engineer?
│   │   ├── YES → Build custom. You have the scale and expertise.
│   │   └── NO → Use Auth0 now. Hire security first, then evaluate.
│   └── NO → Use Auth0. You don't have the scale to justify custom.
├── Is vendor lock-in a hard constraint?
│   ├── YES → Build custom with open standards (OIDC/SAML).
│   └── NO → Auth0 or Clerk. Optimize for speed.
└── Timeline <3 months?
    ├── YES → Auth0. No time to build.
    └── NO → Evaluate both. Run a 2-week spike.
```

### How It Works

The decision tree is generated by the **judge** — it's a prompt addition, not a code feature. We add instructions to the judge system prompt telling it to output a decision tree section.

### Prompt Addition (to judge_addendum)

```
After your verdict, include a DECISION TREE section.

Format it as an ASCII tree using ├──, │, and └── characters.
Start with the original question. Each branch is a YES/NO question
based on the assumptions and conditionals you identified.
Each leaf node is a concrete recommendation.

Rules:
- Max 3 levels deep (keep it actionable, not exhaustive)
- Each question must be something the reader can answer right now
- Leaf recommendations must be specific ("Use Auth0" not "consider options")
- Include the key differentiating factor at each branch
```

### Implementation

| File | Changes |
|------|---------|
| `prompts.py` | Add `DECISION_TREE_ADDENDUM` to judge system prompts |
| `debate.py` | Append addendum in `judge()` stage for adversarial debates |

This is the lightest feature — it's purely a prompt engineering change. No new modules, no new data structures.

### Key Decision: Always or opt-in?

- **(A)** Always include decision tree in adversarial verdicts
- **(B)** `--tree` flag to opt in

Recommend **(A)** — the tree is the most actionable part of the output. If it's opt-in, nobody discovers it.

---

## Build Order

| Order | Feature | Effort | Impact | Dependencies |
|-------|---------|--------|--------|--------------|
| 1 | Decision tree output | 30 min | High | None (prompt-only) |
| 2 | Custom YAML templates | 1-2 hrs | Medium | pyyaml dep |
| 3 | Shareable transcripts | 1-2 hrs | High | None |
| 4 | Outcome tracking | 2-3 hrs | Highest (compounds) | Needs confidence parsing from verdicts |

Start with decision tree (pure prompt, immediate value), end with outcome tracking (most complex, most valuable long-term).

---

## Open Questions

1. **Outcome tracking: where does confidence come from?** The structured verdict includes "confidence: X/10" but parsing free text is fragile. Should we add a structured JSON response from the judge for metadata extraction?

2. **HTML export: dark mode?** Single theme or auto-detect? Leaning toward light theme only for shareability (Slack/email previews).

3. **YAML templates: should we ship example templates in the repo?** A `templates/examples/` directory with launch, acquire, pivot, sunset templates would help discovery.

4. **Decision tree: what about peer debates?** The tree format works best for binary decisions (adversarial). For peer debates, maybe a comparison matrix instead?

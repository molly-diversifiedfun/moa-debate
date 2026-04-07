# Prompts & Context

How moa-debate builds the prompts that get sent to models, and how to inspect/edit them.

---

## How prompts work

Every mode uses structured prompt templates in `src/moa/prompts.py`:

- **Synthesizer prompts** tell the aggregator to output structured sections (Answer, Agreement, Disagreement, Attribution). The models produce markdown that the CLI renders.
- **Challenge prompts** instruct models to find flaws, not just agree. "You MUST identify at least one flaw per response."
- **Persona prompts** inject philosophy: "You think like Rich Hickey. Ask: 'Is this simple or just easy?'"
- **Research context** is injected as reference material with a framing that tells models to reason independently: "Use it if applicable, but do not assume this information is complete."

All prompts live in a single file — edit `src/moa/prompts.py` directly to change model behavior.

---

## How context injection works

When you run `moa ask --context . "How should I structure this?"`:

1. `context.py` scans the directory:
   - Reads README, `package.json` / `pyproject.toml` / `Cargo.toml` (whatever exists)
   - Builds a directory tree (3 levels, 80 items max)
   - Reads `.env.example`
2. Everything gets concatenated and truncated to 12K chars
3. The context is prepended to your query:
   ```
   [PROJECT CONTEXT]
   {context}
   [/PROJECT CONTEXT]

   Question: your query
   ```
4. Models see it as part of the user message — no magic

When you use `/moa` from Claude Code, the slash command shells out to `moa ask`. Pass `--context .` to inject the current project. Without it, models answer generically.

For code review, the git diff is sent as the user message with role-specific system prompts (security, architecture, etc.).

---

## Using your own files as context

```bash
# Point at a single file
moa ask --context ./research.md "Rework this plan for a 2-person team"

# Point at a directory (auto-detects project type)
moa ask --context . "How should I structure this app?"

# Pipe multiple files (they become part of the query)
cat brief.md plan.md | moa ask "Review this plan given the brief. What's missing?"

# Pipe research + ask for a rework
cat research-findings.md | moa ask --persona product "Given this research, should we pivot?"

# Pipe code for review
cat src/auth.py src/middleware.py | moa ask "Find security issues in this code"
```

`--context` and piped input work differently:
- `--context` reads project files and adds structured context (project type, directory tree, key files)
- Piped input (`cat file | moa ask`) sends the raw file content as part of the query
- Both can be used together: `cat notes.md | moa ask --context . "How does this fit my project?"`

---

## Inspecting the full prompt

Use `--debug` to see exactly what gets sent to models:

```bash
moa ask --debug --context . --persona "DHH" "Should I add a cache layer?"
```

This shows the complete prompt after all injections (context + persona + piped input) so you can verify what models actually see. Useful for tweaking — if the answer isn't what you expected, check the prompt first.

---

## Decision templates

Templates give the debate judge domain-specific criteria without constraining what the debaters can argue. Based on Bandi et al. (2024): constraining advocates causes argument collapse. Legal systems constrain roles, not arguments.

### Built-in templates
- `hire` — hiring decisions (senior vs junior, contractor vs FTE)
- `build` — build vs buy (in-house vs vendor)
- `invest` — investment decisions (risk-adjusted returns, liquidity)

### Example templates (install via CLI)
```bash
moa templates --install-examples
```

Installs 6 example templates to `~/.moa/templates/`:
- `startup` — founding team, market entry, MVP validation
- `launch` — soft vs hard launch, timing, first-impression strategy
- `strategy` — competitive positioning, pricing, partnerships
- `acquire` — M&A, acqui-hires, buy vs partner
- `pivot` — when to change direction, what to keep
- `sunset` — when to kill a product, feature, or initiative

### Custom templates
Drop any YAML file into `~/.moa/templates/` matching this shape:

```yaml
name: my-template
description: "Short tagline"
keywords: [kw1, kw2, kw3]  # Auto-detection triggers
debater_context: |
  Light context for both sides. What kind of decision this is, not what to argue.
judge_addendum: |
  ## Evaluation Criteria
  - **Criterion 1**: How to measure this
  - **Criterion 2**: What matters here

  Decision tree should check:
  1. First branching question?
  2. Second branching question?

  De-risk steps must include:
  - Validation approach
  - Success metrics
research_queries:  # Optional
  - "search query 1"
  - "search query 2"
```

Validate before use:
```bash
moa templates validate path/to/my-template.yaml
```

Custom templates take priority over built-ins with the same name.

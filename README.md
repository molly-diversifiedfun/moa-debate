# moa-debate

**One LLM gives one guess. moa-debate picks 3-5 models from different providers for every question, then makes them debate — or searches the web when they disagree.**

![tests](https://img.shields.io/badge/tests-197%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-purple)
![roster](https://img.shields.io/badge/model%20roster-14-orange)

moa-debate is a CLI tool that runs your questions across 3-5 LLMs from different providers (GPT, Claude, Gemini, optionally DeepSeek/Grok/Llama), then synthesizes their responses into a single more reliable answer. Adaptive routing picks the right model count per query — 1 cheap model for factoids, up to 5 frontier models for high-stakes decisions. When they disagree, it automatically searches the web to ground the response in real sources.

![demo](demo.gif)

---

## Table of Contents

- [The Problem](#the-problem)
- [Quick Start](#quick-start)
- [What Can You Do With It?](#what-can-you-do-with-it)
- [Core Concepts](#core-concepts)
- [Commands](#commands)
- [Deep Dives](#deep-dives)
- [Acknowledgments](#acknowledgments)
- [License](#license)

---

## The Problem

Every LLM has blind spots. Claude is great at reasoning but sometimes hallucinates API details. GPT is fast but occasionally misses edge cases. Gemini knows Google's ecosystem cold but may be weaker elsewhere. When you ask a single model a question, you get that model's best guess — including its biases, training gaps, and confident mistakes.

**Multi-model consensus fixes this.** When three models from three different providers independently reach the same conclusion, that conclusion is almost certainly correct. When they disagree, the disagreement itself is the signal — it tells you the question is harder than it looks, and maybe you should look it up.

### Who this is for

- **Developers making architecture decisions** — "Should I use microservices?" gets a more balanced answer from 4 models than from 1
- **Tech leads reviewing code** — 4 specialist reviewers (security, architecture, performance, correctness) across different models catch more bugs than any single reviewer
- **Solopreneurs shipping fast** — ask Pieter Levels and Daniel Vassallo personas: "Can I ship this without a database?"
- **Anyone who wants to trust AI more** — every response shows you the confidence score, where models agreed, where they differed, and which model had the strongest reasoning

---

## Quick Start

```bash
git clone https://github.com/molly-diversifiedfun/moa-debate.git
cd moa-debate
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Recommended: install git hooks (cli import check + pre-push tests)
./hooks/install.sh

# Set API keys (at least one provider required, more = better)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=AI...

# Optional: enables auto-research when models disagree
export FIRECRAWL_API_KEY=fc-...

# Verify what's connected
moa status

# Ask something
moa ask "Should I use microservices or a monolith for a 3-person startup?"
```

### What the output looks like

```
╭──────────── adaptive:standard (STRATEGIC) ⚠️ SPLIT (14%) ─────────────╮
│ ## Answer                                                              │
│ Start with a monolith...                                               │
│                                                                        │
│ ## Where Models Agreed                                                 │
│ - Monolith first for teams under 5                                     │
│ - Microservices add coordination overhead that kills velocity          │
│                                                                        │
│ ## Where Models Differed                                               │
│ - GPT-5.4: emphasized deployment simplicity                            │
│ - Sonnet: focused on team cognitive load                               │
│ - Gemini: raised the "strangler fig" migration pattern                │
│                                                                        │
│ ## Why This Answer                                                     │
│ Gemini's reasoning was strongest because...                            │
╰────────────────────────────────────────────────────────────────────────╯
  Agreement: 87% (3/3 aligned) · Domain: STRATEGIC · Threshold: 20%
  ██████████████████░░ HIGH — models converged
  $0.15 · 12,340 tokens · ⏱ 15.2s · 👑 Best: gemini-2.5-pro
```

---

## What Can You Do With It?

### 🧠 Make better decisions
```bash
moa ask "Redis or Memcached for sessions with 50K DAU?"
moa ask --persona "DHH" "Convince me this microservice is a bad idea"
moa debate --style adversarial "Should we migrate to DynamoDB?"
```

### ⚖️ Compare single model vs ensemble
```bash
moa compare "Should we use Postgres or MongoDB?"
moa compare --single claude-sonnet --ensemble pro "Build auth in-house?"
```

Runs your chosen model AND an ensemble in parallel, then shows them side-by-side with agreement score, pairwise ranking, and cost delta. Useful for seeing whether the ensemble is actually adding value over a single strong model.

### 🔍 Get a real code review
```bash
moa review --staged                              # 4 specialist reviewers
moa review --staged --persona "Sandi Metz"       # "7 params? Limit is 4."
moa review --staged --personas --discourse       # reviewers challenge each other
```

### 💬 Settle team debates
```bash
moa debate "Event sourcing vs CRUD for orders?"
moa debate --style adversarial "Should we rewrite in Rust?"
moa debate --style adversarial --template hire "Senior engineer or two juniors?"
moa debate --style adversarial --template startup "Quit jobs to build this?"
moa debate --persona "DHH,Kelsey Hightower" "Do we need Kubernetes?"
```

Debates are **research-grounded** — both sides get real web sources and cite evidence, and the judge verifies claims. **Circuit breakers** auto-skip broken models. **9 decision templates** (3 built-in + 6 shippable examples installed via `moa templates --install-examples`) add domain-specific judge criteria.

### 📋 Review your plans and research
```bash
cat research.md plan.md | moa ask "Is this plan solid? What am I missing?"
cat plan.md | moa debate --style adversarial "Should we quit our jobs and execute this?"
```

### 🚀 Ship faster as a solopreneur
```bash
moa ask --persona builder "Fastest path to first revenue for an invoice SaaS?"
moa ask --persona "Pieter Levels" "Can I ship this without a database?"
```

### 🔎 Verify things you don't trust
```bash
moa ask "Does AWS Lambda still have a 15-min timeout?"   # cross-model fact check
moa ask --research deep "Firecrawl API rate limits"      # grounded in real docs
moa ask --debug "..."                                     # see exactly what was sent
```

> 📖 For the full situational guide with 12 real scenarios, see **[docs/USE_CASES.md](docs/USE_CASES.md)**.

---

## Core Concepts

> 🧭 **Adaptive routing**: queries are auto-classified by complexity + domain and routed to the right model pool. You don't configure this.

> 🌐 **Research-augmented**: when models disagree, the system searches the web via Firecrawl (or DuckDuckGo fallback) and re-asks with grounded context.

> 👑 **Pairwise ranking**: a cheap model compares responses to pick the genuinely best one instead of the longest.

> 📊 **Trust signals**: every response shows confidence, agreement score, per-model attribution, and warnings for correlated hallucination.

> ⚙️ **Composable debate pipelines**: both peer and adversarial debates run as `state → stages → format_result`. Swap stages to customize without rewriting.

> 🧪 **Layered quality checks**: tests assert structural format, pipeline invariants, and (optionally) LLM-as-judge rubric scores.

> 📖 Full technical details in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Commands

```bash
moa ask "..."                     # Multi-model query (adaptive routing)
moa compare "..."                 # Single model vs ensemble side-by-side
moa debate "..."                  # Multi-round debate (peer or adversarial)
moa review --staged               # Expert panel code review
moa outcome list --stats          # Accuracy tracking for past debates
moa templates                     # List decision templates
moa templates --install-examples  # Copy 6 example templates to ~/.moa/templates/
moa status                        # Model roster, API keys, budget
moa verify                        # Ping all models
moa health                        # Circuit breaker status
moa test                          # Automated smoke tests
moa history --cost                # Spend tracking
moa serve                         # HTTP API server
```

<details>
<summary><b>All flags (click to expand)</b></summary>

| Flag | Commands | Default | Description |
|------|----------|---------|-------------|
| `--persona` | ask, debate, review | — | Persona names or category |
| `--research` | ask | `auto` | `auto`, `lite`, `deep`, `off` |
| `--style` | debate | `peer` | `peer`, `adversarial` |
| `--template` | debate | auto-detect | `hire`, `build`, `invest`, or custom YAML |
| `--export` | debate | — | Export transcript: `html` or `md` |
| `--discourse` | review | off | Reviewers react to each other |
| `--personas` | review | off | Use code review personas |
| `--layers` | ask | 1 | Aggregation layers (1-3) |
| `--tier` | ask, debate | auto | `flash`, `lite`, `pro`, `ultra` |
| `--context` | ask, debate | — | Path for context injection |
| `--rounds` | debate | 2 | Debate rounds |
| `--single` | compare | `auto` | Single model name (or `auto` for best available) |
| `--ensemble` | compare | `lite` | Ensemble tier: `flash`, `lite`, `pro`, `ultra` |
| `--install-examples` | templates | off | Copy 6 example templates to `~/.moa/templates/` |
| `--raw` | all | off | Plain text (for piping) |
| `--no-cache` | ask | off | Bypass cache |
| `--debug` | ask | off | Show full prompt sent to models |

</details>

<details>
<summary><b>Personas (14 across 5 categories)</b></summary>

| Category | Personas | Ask them about |
|----------|----------|---------------|
| **code** | Fowler, Beck, Hickey, Metz | Refactoring, testing, complexity, SRP |
| **architecture** | Hightower, Kleppmann, DHH | Infra, distributed systems, simplicity |
| **product** | Doshi, Cagan, Dunford | Leverage, discovery, positioning |
| **content** | Ogilvy, Handley | Headlines, copy, clarity |
| **builder** | Levels, Vassallo | Shipping fast, small bets |

```bash
moa ask --persona "DHH,Kent Beck" "..."     # by name (fuzzy matching)
moa ask --persona product "..."             # all personas in a category
```

Full bios and philosophies: **[docs/PERSONAS.md](docs/PERSONAS.md)**

</details>

---

## Deep Dives

| Topic | Read |
|---|---|
| 🏗  How it's built, module map, design decisions | **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** |
| 💬 Prompts, context injection, templates, `--debug` | **[docs/PROMPTS.md](docs/PROMPTS.md)** |
| 🧪 Tests, quality checks, e2e tiers, git hooks | **[docs/TESTING.md](docs/TESTING.md)** |
| ⚙️  Env vars, state files, HTTP API, Claude Code | **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** |
| 📖 12 real-world use case walkthroughs | **[docs/USE_CASES.md](docs/USE_CASES.md)** |
| 👥 Who the 14 personas are and what they catch | **[docs/PERSONAS.md](docs/PERSONAS.md)** |

---

## Acknowledgments

Techniques adapted from:
- [togethercomputer/MoA](https://github.com/togethercomputer/MoA) — multi-layer aggregation, the original Mixture-of-Agents paper
- [msitarzewski/duh](https://github.com/msitarzewski/duh) — challenge rounds, convergence exit, domain-capped confidence
- [spencermarx/open-code-review](https://github.com/spencermarx/open-code-review) — reviewer discourse, famous engineer personas
- [Skytliang/Multi-Agents-Debate](https://github.com/Skytliang/Multi-Agents-Debate) — angel/devil/judge debate pattern
- [yuchenlin/LLM-Blender](https://github.com/yuchenlin/LLM-Blender) — pairwise ranking for response selection

---

## License

MIT

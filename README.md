# moa-debate

**Ask one AI a question, you get one perspective. Ask fourteen, you get the truth.**

moa-debate is a CLI tool that runs your questions through multiple AI models in parallel — GPT, Claude, Gemini, DeepSeek, Grok, Llama — and synthesizes their responses into a single, more reliable answer. When models disagree, it automatically searches the web to ground the response in real documentation.

## The Problem

Every LLM has blind spots. Claude is great at reasoning but sometimes hallucinates API details. GPT is fast but occasionally misses edge cases. Gemini knows Google's ecosystem cold but may be weaker elsewhere. When you ask a single model a question, you get that model's best guess — including its biases, training gaps, and confident mistakes.

**Multi-model consensus fixes this.** When three models from three different providers independently reach the same conclusion, that conclusion is almost certainly correct. When they disagree, the disagreement itself is the signal — it tells you the question is harder than it looks, and maybe you should look it up.

## Who This Is For

- **Developers making architecture decisions** — "Should I use microservices?" gets a more balanced answer from 4 models than from 1
- **Tech leads reviewing code** — 4 specialist reviewers (security, architecture, performance, correctness) across different models catch more bugs than any single reviewer
- **Solopreneurs shipping fast** — ask Pieter Levels and Daniel Vassallo personas for advice: "Can I ship this without a database?"
- **Anyone who wants to trust AI more** — every response shows you the confidence score, where models agreed, where they differed, and which model had the strongest reasoning

## How It Works

```
You ask a question
    ↓
Classifier determines complexity (SIMPLE/STANDARD/COMPLEX)
and domain (FACTUAL/TECHNICAL/CREATIVE/JUDGMENT/STRATEGIC)
    ↓
Routes to the right model pool (1 cheap model for simple, 3-4 frontier models for complex)
    ↓
Models answer independently in parallel
    ↓
Agreement detection with domain-specific thresholds
(factual questions need 45% agreement, strategic only 20%)
    ↓
┌─ High agreement → Synthesize best elements
└─ Low agreement → Search the web → Re-ask with docs → Synthesize
    ↓
If STRATEGIC/JUDGMENT → add "It Depends On..." + "How to De-Risk This"
    ↓
Output: Answer + Confidence + Agreement/Disagreement + Attribution + Conditionals
```

### What makes this different from just asking Claude?

1. **Independent verification.** Models from different companies with different training data agree or disagree. Agreement = high confidence. Disagreement = worth investigating.
2. **Automatic research.** When models disagree on facts, the system searches the web and re-asks with documentation. You get grounded answers, not guesses.
3. **Transparency.** Every response shows you the agreement score, which model said what, and why the synthesizer chose one model's reasoning over another. You can verify instead of trust.
4. **Actionable for decisions.** Strategic and judgment questions automatically get "It Depends On..." conditional analysis and "How to De-Risk This" steps. Not just "here's the answer" but "here's what to do next."
5. **Cost-aware routing.** Simple questions hit one cheap model (~$0.001). Complex questions use frontier models (~$0.15). You don't pay $0.25 to answer "What port does HTTP use?"

## Quick Start

```bash
git clone https://github.com/molly-diversifiedfun/moa-debate.git
cd moa-debate
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

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

## Core Concepts

### Adaptive Routing

Every query is classified by complexity and domain. Simple factual questions hit 1-2 cheap models. Complex strategic questions use 3-4 frontier models with synthesis. You never configure this — it just works.

### Domain-Aware Responses

Every query is classified into a domain. This affects two things: (1) how much model agreement is needed before triggering research, and (2) whether the response includes conditional analysis and de-risking steps.

| Domain | Agreement Threshold | Extra Output |
|--------|-----------|-----|
| FACTUAL | 45% | Standard answer |
| TECHNICAL | 40% | Standard answer |
| CREATIVE | 30% | Standard answer |
| JUDGMENT | 25% | + "It Depends On..." + "How to De-Risk This" |
| STRATEGIC | 20% | + "It Depends On..." + "How to De-Risk This" |

For STRATEGIC and JUDGMENT queries, the synthesizer automatically adds:
- **It Depends On...** — conditional scenarios where the answer changes ("If you've validated with 10+ users, then X. If this is just an idea, then Y.")
- **How to De-Risk This** — 3-5 specific steps you can do in days, not months

This means `moa ask "Should I take equity or salary?"` automatically gets de-risking analysis — no special flag needed.

### Research-Augmented Routing

When models disagree, the system:
1. Uses a cheap model to derive 2-3 search queries
2. Searches the web via [Firecrawl](https://firecrawl.dev) (falls back to DuckDuckGo if no Firecrawl key — free, no API key needed)
3. Re-asks the same models with reference docs injected
4. Synthesizes with source attribution

This prevents the biggest failure mode of multi-model consensus: **correlated hallucination**. When all models share the same training gap (e.g., niche tooling), they confidently guess different wrong answers. Research grounds them in reality.

You can also force deep research: `moa ask --research deep "query"` runs 2-3 rounds of web search, identifies gaps, and synthesizes with a single frontier model.

### Pairwise Ranking

Instead of picking the longest response (a common but terrible heuristic), a cheap model compares responses pairwise to select the genuinely best one. The footer shows `👑 Best: model-name`.

### Trust Signals

Every response includes transparency features:
- **Confidence bar** (██████░░░░) with HIGH/MODERATE/MIXED/LOW label
- **Correlated confidence warning** — alerts you when high agreement on a niche topic might be shared hallucination
- **Factual verification** — on factual queries, checks for suspicious precision and conflicting numbers
- **Session memory** — tracks previous answers to flag contradictions within a session

## Usage: What Can You Do?

### Make better decisions
```bash
moa ask "Redis or Memcached for sessions with 50K DAU?"
moa ask --persona "DHH" "Convince me this microservice is a bad idea"
moa debate --style adversarial "Should we migrate to DynamoDB?"
```

### Get a real code review
```bash
moa review --staged                              # 4 specialist reviewers
moa review --staged --persona "Sandi Metz"       # "7 params? Limit is 4."
moa review --staged --personas --discourse       # reviewers challenge each other
```

### Review your plans and research
```bash
cat research.md plan.md | moa ask "Is this plan solid? What am I missing?"
cat plan.md | moa ask --persona product "Is this discovery or delivery theater?"
cat plan.md | moa debate --style adversarial "Should we quit our jobs and execute this plan?"
```

Adversarial debate on a plan produces: verdict, key assumptions flagged, conditional analysis ("if you've validated demand, then X; if not, then Y"), and specific de-risking steps you can do in days, not months.

### Ship faster as a solopreneur
```bash
moa ask --persona builder "Fastest path to first revenue for an invoice SaaS?"
moa ask --persona "Pieter Levels" "Can I ship this without a database?"
```

### Verify things you don't trust
```bash
moa ask "Does AWS Lambda still have a 15-min timeout?"   # cross-model fact check
moa ask --research deep "Firecrawl API rate limits"      # grounded in real docs
moa ask --debug "..."                                     # see exactly what was sent
```

### Write better copy
```bash
moa ask --persona "David Ogilvy" "Write 5 headlines for this landing page"
moa ask --persona "Ann Handley" "Would a real person say this out loud?"
```

### Settle team debates
```bash
moa debate "Event sourcing vs CRUD for orders?"
moa debate --style adversarial "Should we rewrite in Rust?"
moa debate --style adversarial --template hire "Senior engineer or two juniors?"
moa debate --style adversarial --template build "Build auth in-house or use Auth0?"
moa debate --persona "DHH,Kelsey Hightower" "Do we need Kubernetes?"
```

Debates are **research-grounded** — both sides get real web sources and cite evidence, and the judge verifies claims. **Circuit breakers** auto-skip broken models and pick the next-strongest. **Decision templates** (`--template hire|build|invest`) add domain-specific judge criteria. Auto-extends rounds if positions are still shifting, exits early on convergence.

For the full situational guide with 12 real scenarios, see **[docs/USE_CASES.md](docs/USE_CASES.md)**.

### Personas (14 perspectives across 5 categories)

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

**Who are these people?** See **[docs/PERSONAS.md](docs/PERSONAS.md)** — each persona's philosophy, what they catch that others miss, key works, and reference links.

### All Commands

```bash
moa ask "..."           # Multi-model query (adaptive routing)
moa debate "..."        # Multi-round debate with challenge rounds
moa review --staged     # Expert panel code review
moa outcome list        # View debate outcomes + accuracy stats
moa outcome log <id>    # Record what you decided
moa outcome tag <id>    # Record what happened (closes feedback loop)
moa status              # Model roster, API keys, budget
moa verify              # Ping all models
moa health              # Circuit breaker status for all models
moa templates           # List available decision templates
moa test                # Automated smoke tests
moa history --cost      # Spend tracking
moa serve               # HTTP API server
```

## Architecture

### 14 Models, 6 Providers

**Core** (need at least one): Anthropic (Opus, Sonnet, Haiku), OpenAI (GPT-5.4, GPT-4.1, 4o-mini), Google (Gemini 3.1 Pro, 2.5 Pro, Flash)

**Optional** (auto-included when keys are set): DeepSeek (V3, R1), xAI (Grok 4, 4.1-fast), Together/Meta (Llama-4-Maverick)

### 4 Tiers

| Tier | Models | Aggregator | Cost | When |
|------|--------|-----------|------|------|
| flash | Gemini Flash | none | ~$0.001 | Factoids, lookups |
| lite | 4o-mini, Flash | Sonnet | ~$0.05 | Standard questions |
| pro | GPT-4.1, Gemini Pro, Haiku | Sonnet | ~$0.09 | Reasoning, analysis |
| ultra | GPT-5.4, Gemini 3.1, Sonnet | Opus | ~$0.25 | High-stakes decisions |

### Design Decisions

**Why multiple providers, not multiple models from one provider?**
Models from the same provider share training data and biases. GPT-4.1 and GPT-5.4 will often make the same mistakes. True diversity requires different companies, different training pipelines, different architectural decisions.

**Why domain-capped thresholds instead of a flat agreement score?**
A flat 35% threshold triggers research too aggressively on opinion questions (where disagreement is expected) and not aggressively enough on factual questions (where disagreement means someone's hallucinating).

**Why a challenge round before debate revision?**
Without it, models tend to converge on the first answer that sounds reasonable (sycophantic agreement). Forcing them to find flaws first produces genuinely stronger arguments. Inspired by [duh](https://github.com/msitarzewski/duh).

**Why pairwise ranking instead of just picking the longest response?**
Longer isn't better. A concise, correct answer should beat a verbose, hedging one. Pairwise comparison with a cheap model (~$0.003) catches this. Inspired by [LLM-Blender](https://github.com/yuchenlin/LLM-Blender).

**Why research on disagreement instead of on every query?**
Most queries don't need web search — the models know the answer. Search adds 3-5 seconds of latency and costs Firecrawl credits. By only triggering on disagreement, you get the benefit when it matters and skip the overhead when it doesn't.

**Why personas instead of just "review this code"?**
Different reviewers catch different things. A security specialist finds injection vulnerabilities. Sandi Metz finds classes with too many responsibilities. Rich Hickey finds unnecessary complexity. Generic "review this" misses the specific angles that matter.

### How Prompts Work

Every mode uses structured prompt templates in `src/moa/prompts.py`:

- **Synthesizer prompts** tell the aggregator to output structured sections (Answer, Agreement, Disagreement, Attribution). The models produce markdown that the CLI renders.
- **Challenge prompts** instruct models to find flaws, not just agree. "You MUST identify at least one flaw per response."
- **Persona prompts** inject philosophy: "You think like Rich Hickey. Ask: 'Is this simple or just easy?'"
- **Research context** is injected as reference material with a framing that tells models to reason independently: "Use it if applicable, but do not assume this information is complete."

### How Context Injection Works

When you run `moa ask --context . "How should I structure this?"`:

1. `context.py` scans the directory: reads README, package.json/pyproject.toml/Cargo.toml (whatever exists), builds a directory tree (3 levels, 80 items max), reads .env.example
2. Everything gets concatenated and truncated to 12K chars
3. The context is prepended to your query: `[PROJECT CONTEXT]\n{context}\n[/PROJECT CONTEXT]\n\nQuestion: your query`
4. Models see it as part of the user message — no magic

When you use `/moa` from Claude Code, the slash command shells out to `moa ask`. Pass `--context .` to inject the current project. Without it, models answer generically.

For code review, the git diff is sent as the user message with role-specific system prompts (security, architecture, etc.).

**Using your own files as context:**

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

Piped input and `--context` work differently:
- `--context` reads project files and adds structured context (project type, directory tree, key files)
- Piped input (`cat file | moa ask`) sends the raw file content as part of the query
- Both can be used together: `cat notes.md | moa ask --context . "How does this fit my project?"`

### Inspecting the Full Prompt

Use `--debug` to see exactly what gets sent to models:

```bash
moa ask --debug --context . --persona "DHH" "Should I add a cache layer?"
```

This shows the complete prompt after all injections (context + persona + piped input) so you can verify what models actually see. Useful for tweaking — if the answer isn't what you expected, check the prompt first.

All system prompts live in `src/moa/prompts.py` — edit them directly to change model behavior.

### Module Map

```
src/moa/
├── cli.py           # Typer CLI (11 commands)
├── engine.py        # Re-export layer (backward compat)
├── orchestrator.py  # Model calls, cost tracking, agreement, ranking
├── adaptive.py      # Adaptive routing, MoA, cascade, deep research
├── debate.py        # Peer + adversarial debate (composable pipeline)
├── review.py        # Expert panel code review
├── events.py        # Typed event system (EventType enum + DebateEvent)
├── export.py        # Shareable transcript export (HTML + markdown)
├── outcomes.py      # Outcome tracking (verdict → decision → result)
├── models.py        # 14 models, 4 tiers, 14 personas, reviewer roles
├── templates.py     # Decision templates (built-in + custom YAML)
├── health.py        # Circuit breakers, health-aware model selection
├── research.py      # SearchProvider protocol, Firecrawl + DuckDuckGo
├── prompts.py       # All prompt templates
├── server.py        # FastAPI HTTP API (5 endpoints)
├── context.py       # Project context detection + injection
├── config.py        # Constants (timeouts, budget, rate limits)
├── cache.py         # SQLite response caching (1hr TTL)
├── budget.py        # Daily spend cap ($5/day default)
├── history.py       # JSONL query logging
└── verify.py        # Model connectivity test
```

## Configuration

All configuration via environment variables. No config files to manage.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic (Claude) API key |
| `OPENAI_API_KEY` | — | OpenAI (GPT) API key |
| `GEMINI_API_KEY` | — | Google (Gemini) API key |
| `FIRECRAWL_API_KEY` | — | Firecrawl (web search). Optional — enables research |
| `MAX_DAILY_SPEND_USD` | 5.00 | Daily cost cap (0 = unlimited) |
| `MODEL_TIMEOUT_SECONDS` | 45 | Per-model call timeout |
| `CACHE_TTL_HOURS` | 1 | Response cache TTL |
| `MOA_SERVER_KEY` | — | API server auth key |

State files live in `~/.moa/`: usage.json, history.jsonl, cache/cache.db, sessions/, health.json, debates/, outcomes.jsonl, templates/.

## All Flags

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
| `--raw` | all | off | Plain text (for piping) |
| `--no-cache` | ask | off | Bypass cache |
| `--debug` | ask | off | Show full prompt sent to models |

## Claude Code Integration

MOA works as slash commands inside [Claude Code](https://claude.ai/code). Install the commands:

```bash
# Copy slash commands to your Claude Code config
cp claude-code/moa.md ~/.claude/commands/moa.md
cp claude-code/moa-debate.md ~/.claude/commands/moa-debate.md
cp claude-code/moa-review.md ~/.claude/commands/moa-review.md
```

Then in Claude Code:
```bash
/moa "Should we use microservices?"                           # Multi-model query
/moa --persona product "Is this feature worth building?"      # Product personas
/moa --research deep "How do I configure LiteLLM failover?"   # Deep research
/moa-debate --style adversarial "Should we rewrite in Rust?"  # Angel vs devil
/moa-review                                                    # Expert panel review
/moa-review --personas --discourse                            # Persona review with discourse
```

The slash command files are in `claude-code/` — customize them for your setup (update the path to your moa-debate venv).

## HTTP API

```bash
moa serve --port 8787
```

| Endpoint | Method | Body |
|----------|--------|------|
| `/moa` | POST | `{"query": "...", "tier": "lite"}` |
| `/cascade` | POST | `{"query": "..."}` |
| `/review` | POST | `{"diff": "...", "context": "..."}` |
| `/debate` | POST | `{"query": "...", "rounds": 2}` |
| `/health` | GET | — |

## Testing

```bash
pytest          # 26 unit tests
moa test        # 5 live smoke tests (~$0.50)
moa test --full # 8 extended tests (~$1)
moa verify      # Ping all models
```

## Acknowledgments

Techniques adapted from:
- [togethercomputer/MoA](https://github.com/togethercomputer/MoA) — multi-layer aggregation, the original Mixture-of-Agents paper
- [msitarzewski/duh](https://github.com/msitarzewski/duh) — challenge rounds, convergence exit, domain-capped confidence
- [spencermarx/open-code-review](https://github.com/spencermarx/open-code-review) — reviewer discourse, famous engineer personas
- [Skytliang/Multi-Agents-Debate](https://github.com/Skytliang/Multi-Agents-Debate) — angel/devil/judge debate pattern
- [yuchenlin/LLM-Blender](https://github.com/yuchenlin/LLM-Blender) — pairwise ranking for response selection

## License

MIT

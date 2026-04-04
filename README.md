# moa-debate

Multi-model AI debate system. Runs queries through diverse AI models in parallel (GPT, Claude, Gemini, DeepSeek, Grok, Llama), synthesizes their responses, and auto-searches the web when models disagree on niche topics.

**Why?** A single LLM has blind spots. Multiple models from different providers catch different errors, surface different perspectives, and produce more reliable answers — especially for architecture decisions, code review, and fact-checking.

## Install

```bash
git clone https://github.com/molly-diversifiedfun/moa-debate.git
cd moa-debate
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## API Keys

Set at least one provider. More providers = more diverse perspectives.

```bash
# Core (at least one required)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=AI...

# Optional — adds model diversity
export DEEPSEEK_API_KEY=...
export XAI_API_KEY=...
export TOGETHER_API_KEY=...

# Optional — enables research-augmented routing
export FIRECRAWL_API_KEY=fc-...

# Verify what's available
moa status
```

## Usage

### Ask a question (adaptive routing)

```bash
moa ask "Should I use microservices or a monolith for a 3-person startup?"
```

Adaptive routing classifies your query by complexity (SIMPLE/STANDARD/COMPLEX) and domain (FACTUAL/TECHNICAL/CREATIVE/JUDGMENT/STRATEGIC), routes to the right models, and applies domain-aware agreement thresholds. If models disagree and you have a Firecrawl key, it automatically searches the web for reference material and re-asks with context.

### Personas

14 named personas across 5 categories. Use on any command — ask, debate, or review.

```bash
# By name (comma-separated, fuzzy matching)
moa ask --persona "DHH,Pieter Levels" "Should I add a database to my side project?"
moa debate --persona "Shreya Doshi,April Dunford" "How should we position this product?"
moa review --staged --persona "Rich Hickey,Kent Beck"

# By category
moa ask --persona product "Is this feature worth building?"
moa debate --persona architecture "Kubernetes vs serverless for a 5-person team?"
moa review --staged --persona code
```

| Category | Personas | Best for |
|----------|----------|----------|
| **code** | Martin Fowler, Kent Beck, Rich Hickey, Sandi Metz | Code review, refactoring, testing |
| **architecture** | Kelsey Hightower, Martin Kleppmann, DHH | Infrastructure, distributed systems, simplicity |
| **product** | Shreya Doshi, Marty Cagan, April Dunford | Product strategy, positioning, prioritization |
| **content** | David Ogilvy, Ann Handley | Copy, headlines, voice, clarity |
| **builder** | Pieter Levels, Daniel Vassallo | Shipping fast, small bets, solopreneur decisions |

### Research mode

```bash
# Auto-search on disagreement (default — no flag needed)
moa ask "How do I configure Claude Code hooks in settings.json?"

# Force deep multi-hop research
moa ask --research deep "What are the best practices for LiteLLM provider failover?"

# Disable research
moa ask --research off "What's the capital of France?"
```

Deep research runs 2-3 rounds of web search via Firecrawl, identifies gaps, searches deeper, then synthesizes with a single frontier model. Takes 30-60 seconds but grounds answers in real documentation.

### Code review (Expert Panel)

```bash
# Default: 4 specialist reviewers
moa review --staged

# Famous engineer personas
moa review --staged --personas
moa review --staged --persona "Rich Hickey,Sandi Metz"

# With discourse: reviewers react to each other's findings
moa review --staged --discourse

# Combine: personas + discourse
moa review --staged --personas --discourse

# Pipe from git
git diff main..feature-branch | moa review
```

**Default specialists:** Security (GPT-4.1), Architecture (Sonnet), Performance (Gemini 2.5 Pro), Correctness (Gemini 3.1 Pro)

**Discourse mode** (`--discourse`): After the initial review, each reviewer sees all other findings and can AGREE, CHALLENGE, CONNECT, or SURFACE new issues. Catches cross-cutting problems that isolated reviewers miss.

### Multi-round debate

```bash
# Peer debate (default) — models challenge each other, then revise
moa debate "Monorepo vs polyrepo for 4 brands?"

# Adversarial debate — angel argues FOR, devil argues AGAINST, judge synthesizes
moa debate --style adversarial "Should we rewrite in Rust?"

# With personas
moa debate --persona "DHH,Kelsey Hightower" "Do we need Kubernetes?"

# More rounds
moa debate --rounds 3 "Event sourcing vs CRUD for order management?"
```

**Peer debates** now include a forced challenge round (models must find flaws before revising) and auto-exit when models converge (saves cost on early agreement).

**Adversarial debates** assign explicit roles: one model advocates FOR, one argues AGAINST, and a judge synthesizes both perspectives.

### Multi-layer aggregation

```bash
# Standard: proposers → aggregator (1 layer, default)
moa ask --tier pro "Compare ORMs for Next.js"

# Verified: proposers → aggregator → proposers verify → re-aggregate (2 layers)
moa ask --tier pro --layers 2 "Design a payment processing pipeline"
```

Layer 2 re-runs proposers on the synthesis to catch aggregator errors. Recommended for complex queries where accuracy matters more than speed.

### Manual tier selection

```bash
moa ask --tier flash "What's 2+2?"          # ~$0.001, 1s
moa ask --tier lite "Explain useEffect"      # ~$0.05, 8s
moa ask --tier pro "Compare ORMs for Next.js" # ~$0.09, 15s
moa ask --tier ultra "Design a payment system" # ~$0.25, 20s
```

### Other commands

```bash
moa status                # Model roster, API key status, budget
moa verify                # Test connectivity to all models
moa history --last 20     # Recent queries
moa history --cost        # Daily spend summary
moa serve --port 8787     # Start HTTP API server
```

## Architecture

### 4 Query Modes

| Mode | Trigger | What happens | Cost |
|------|---------|-------------|------|
| **Adaptive** (default) | `moa ask` | Classify → route → propose → domain-capped agreement → pairwise rank → synthesize. Auto-researches on disagreement. | $0.001–$0.15 |
| **Deep Research** | `--research deep` | Multi-hop web search → single frontier model with full context | $0.15–$0.30 |
| **Cascade** (legacy) | `--cascade` | Lite → evaluate confidence → escalate to ultra if needed | $0.05–$0.30 |
| **Debate** | `moa debate` | Challenge round → multi-round revision → convergence check → judge | $0.20–$0.40 |

### Smart Agreement Detection

Agreement thresholds are domain-aware (inspired by [duh](https://github.com/msitarzewski/duh)):

| Domain | Threshold | Rationale |
|--------|-----------|-----------|
| FACTUAL | 45% | Models should agree on facts |
| TECHNICAL | 40% | Some implementation opinions OK |
| CREATIVE | 30% | Diversity expected |
| JUDGMENT | 25% | Opinion splits are normal |
| STRATEGIC | 20% | Complex decisions always diverge |

Below threshold → research + re-ask. Above → synthesize.

Additionally, proposals are pairwise-ranked by a cheap model (inspired by [LLM-Blender](https://github.com/yuchenlin/LLM-Blender)) to pick the best response, not just the longest.

### 4-Tier Model System

| Tier | Proposers | Aggregator | Cost |
|------|-----------|-----------|------|
| **flash** | Gemini Flash | none | ~$0.001 |
| **lite** | 4o-mini, Flash (+optional) | Sonnet | ~$0.05 |
| **pro** | GPT-4.1, Gemini 2.5 Pro, Haiku (+optional) | Sonnet | ~$0.09 |
| **ultra** | GPT-5.4, Gemini 3.1 Pro, Sonnet (+optional) | Opus | ~$0.25 |

### 14 Models, 6 Providers

**Core** (need at least one): Anthropic (Opus, Sonnet, Haiku), OpenAI (GPT-5.4, GPT-4.1, 4o-mini), Google (Gemini 3.1 Pro, 2.5 Pro, Flash)

**Optional** (bonus diversity): DeepSeek (V3, R1), xAI (Grok 4, 4.1-fast), Together/Meta (Llama-4-Maverick)

Optional models are automatically included when their API keys are set. No configuration needed.

### Research-Augmented Routing

When adaptive routing detects low agreement (below domain-specific threshold), it:
1. Derives 2-3 search queries using a cheap model (Haiku/Flash)
2. Searches the web via Firecrawl (2-3 results)
3. Re-runs the same proposers with reference material injected
4. Synthesizes with source attribution

Requires `FIRECRAWL_API_KEY`. Falls back gracefully without it.

### Debate Flow (with improvements from [duh](https://github.com/msitarzewski/duh) and [Multi-Agents-Debate](https://github.com/Skytliang/Multi-Agents-Debate))

**Peer debate:**
```
Round 0: Independent responses
Challenge: Models find flaws in each other's responses (forced disagreement)
Round 1-N: Models revise, addressing challenges
Convergence check: exit early if agreement >70%
Final: Judge synthesizes
```

**Adversarial debate** (`--style adversarial`):
```
Round 0: Angel argues FOR, Devil argues AGAINST
Round 1-N: Each sees the other's position and revises
Convergence check: exit early if agreement >70%
Final: Judge synthesizes both perspectives
```

### Module Map

```
src/moa/
├── cli.py        # Typer CLI (9 commands)
├── engine.py     # Core: adaptive routing, cascade, debate, review, deep research
├── models.py     # 14 models, 4 tiers, 14 personas, reviewer roles
├── research.py   # SearchProvider protocol, Firecrawl integration, lite/deep search
├── server.py     # FastAPI HTTP API (5 endpoints)
├── prompts.py    # System prompts for synthesis/debate/review/research
├── context.py    # Project context detection + injection
├── config.py     # Constants (timeouts, budget, rate limits)
├── cache.py      # SQLite response caching (1hr TTL)
├── budget.py     # Daily spend cap + tracking
├── history.py    # JSONL query logging
└── verify.py     # Model connectivity test
```

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

Optional auth via `X-MOA-Key` header (set `MOA_SERVER_KEY` env var).

## Claude Code Integration

MOA integrates with [Claude Code](https://claude.ai/code) as slash commands:

```bash
/moa "question"              # Adaptive routing query
/moa-review                  # Expert panel on current changes
/moa-debate "question"       # Multi-round debate
```

## Example Use Cases

### Quick questions (~$0.001, 1-3s)
```bash
moa ask "What's the difference between useEffect and useLayoutEffect?"
moa ask "How do I create a temporary table in PostgreSQL?"
```

### Design decisions with personas (~$0.05-0.15, 8-15s)
```bash
moa ask --persona product "Should we build this feature or buy a SaaS tool?"
moa ask --persona "Shreya Doshi" "Is this high-leverage work or just busy work?"
moa ask --persona "April Dunford" "How should we position against Notion?"
```

### Architecture review (~$0.15, 15-30s)
```bash
moa ask "Critique this architecture: Next.js → tRPC → PostgreSQL → Redis → S3."
moa ask --persona architecture "Do we need a message queue for 1000 events/day?"
moa ask --persona "DHH" "Is this microservice justified?"
```

### Content and copy review
```bash
moa ask --persona content "Review this landing page headline for clarity and impact"
moa ask --persona "David Ogilvy" "Does this ad copy make a specific promise?"
moa ask --persona "Ann Handley" "Would a real person say this out loud?"
```

### Solopreneur decisions
```bash
moa ask --persona builder "Should I build an audience first or the product first?"
moa ask --persona "Pieter Levels" "Can I ship this without a database?"
moa ask --persona "Daniel Vassallo" "What's the minimum viable test for this idea?"
```

### Security review via pipe
```bash
cat src/auth/middleware.ts | moa ask --raw "Analyze this for security vulnerabilities"
git diff HEAD~3 | moa ask --raw "What are the riskiest changes in this diff?"
```

### Code review with famous engineers
```bash
moa review --staged --persona "Rich Hickey"    # "Is this simple or just easy?"
moa review --staged --persona "Kent Beck"      # "Where are the missing tests?"
moa review --staged --persona "Sandi Metz"     # "This class does too much"
moa review --staged --discourse                # Reviewers react to each other
```

### Niche tooling questions (auto-researched)
```bash
moa ask "How do I configure Vercel Workflow DevKit for step-based execution?"
moa ask --research deep "What are the current best practices for LiteLLM fallback chains?"
```

### Adversarial debates
```bash
moa debate --style adversarial "Should we rewrite the backend in Rust?"
moa debate --style adversarial --persona "DHH,Kelsey Hightower" "Do we need Kubernetes?"
```

### Multi-round peer debates (~$0.20-0.40, 30-60s)
```bash
moa debate "Is it better to use TypeScript strict mode from day one or add it incrementally?"
moa debate --rounds 3 "GraphQL gateway vs REST with BFF pattern?"
moa debate --persona product "Build vs buy for analytics?"
```

### Fact validation
```bash
moa ask "Is it true that React Server Components can't use useState? Verify with specifics."
moa ask "Does AWS Lambda still have a 15-minute timeout limit as of 2026?"
```

### Multi-layer verification
```bash
moa ask --layers 2 "Design a payment processing pipeline with idempotency guarantees"
```

## All Flags

| Flag | Commands | Default | Options |
|------|----------|---------|---------|
| `--persona` | ask, debate, review | none | Names: `"DHH,Kent Beck"` or category: `code`, `product`, `content`, `architecture`, `builder` |
| `--research` | ask | `auto` | `auto`, `lite`, `deep`, `off` |
| `--style` | debate | `peer` | `peer`, `adversarial` |
| `--discourse` | review | off | Flag — enables reviewer discourse round |
| `--personas` | review | off | Flag — uses default code review personas |
| `--layers` | ask | 1 | 1-3 aggregation layers |
| `--tier` | ask, debate | varies | `flash`, `lite`, `pro`, `ultra` |
| `--context` | ask, debate | none | Path to project for context injection |
| `--rounds` | debate | 2 | Number of debate rounds |
| `--raw` | ask, debate, review | off | Plain text output |
| `--no-cache` | ask | off | Bypass response cache |
| `--cascade` | ask | off | Legacy cascade flow |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_DAILY_SPEND_USD` | 5.00 | Daily cost cap (0 = unlimited) |
| `MODEL_TIMEOUT_SECONDS` | 45 | Per-model call timeout |
| `AGGREGATOR_TIMEOUT_SECONDS` | 60 | Aggregator timeout |
| `CACHE_TTL_HOURS` | 1 | Response cache TTL |
| `MOA_SERVER_KEY` | none | API server auth key |

Budget and history are tracked in `~/.moa/` (usage.json, history.jsonl, cache/cache.db).

## Testing

```bash
pytest               # 26 tests
pytest -v            # Verbose
moa verify           # Test live model connectivity
```

## Acknowledgments

Techniques adapted from:
- [togethercomputer/MoA](https://github.com/togethercomputer/MoA) — multi-layer aggregation
- [msitarzewski/duh](https://github.com/msitarzewski/duh) — challenge rounds, convergence exit, domain-capped confidence
- [spencermarx/open-code-review](https://github.com/spencermarx/open-code-review) — reviewer discourse, famous engineer personas
- [Skytliang/Multi-Agents-Debate](https://github.com/Skytliang/Multi-Agents-Debate) — angel/devil/judge pattern
- [yuchenlin/LLM-Blender](https://github.com/yuchenlin/LLM-Blender) — pairwise ranking

## License

MIT

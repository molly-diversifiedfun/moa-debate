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

Adaptive routing classifies your query as SIMPLE/STANDARD/COMPLEX, routes to the right models, detects agreement, and synthesizes. If models disagree and you have a Firecrawl key, it automatically searches the web for reference material and re-asks with context.

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
# Review staged changes
moa review --staged

# Review a diff file
moa review path/to/changes.diff

# Pipe from git
git diff main..feature-branch | moa review
```

Four specialist reviewers analyze your code in parallel:
- **Security** (GPT-4.1) — injection, auth, secrets, OWASP
- **Architecture** (Sonnet) — SOLID, coupling, async patterns
- **Performance** (Gemini 2.5 Pro) — complexity, N+1, memory
- **Correctness** (Gemini 3.1 Pro) — logic, edge cases, types

An aggregator (Opus) synthesizes findings into severity buckets with a clear APPROVE / REQUEST CHANGES / BLOCK verdict.

### Multi-round debate

```bash
moa debate "Monorepo vs polyrepo for 4 brands?"
moa debate --rounds 3 "Event sourcing vs CRUD for order management?"
```

Models independently answer, then see each other's responses and revise over multiple rounds. A judge synthesizes the final positions.

### Manual tier selection

```bash
moa ask --tier flash "What's 2+2?"          # ~$0.001, 1s
moa ask --tier lite "Explain useEffect"      # ~$0.05, 8s
moa ask --tier pro "Compare ORMs for Next.js" # ~$0.09, 15s
moa ask --tier ultra "Design a payment system" # ~$0.25, 20s
```

### Legacy cascade

```bash
moa ask --cascade "Explain the CAP theorem tradeoffs for Supabase"
```

Starts with a lite pass. If models disagree or the topic is high-stakes, auto-escalates to ultra.

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
| **Adaptive** (default) | `moa ask` | Classify → route → propose → detect agreement → synthesize. Auto-searches web on disagreement. | $0.001–$0.15 |
| **Deep Research** | `--research deep` | Multi-hop web search → single frontier model with full context | $0.15–$0.30 |
| **Cascade** (legacy) | `--cascade` | Lite → evaluate confidence → escalate to ultra if needed | $0.05–$0.30 |
| **Debate** | `moa debate` | Multi-round: independent → see others → revise → judge | $0.20–$0.40 |

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

When adaptive routing detects low model agreement (Jaccard similarity <35%), it:
1. Derives 2-3 search queries using a cheap model (Haiku/Flash)
2. Searches the web via Firecrawl (2-3 results)
3. Re-runs the same proposers with reference material injected
4. Synthesizes with source attribution

This prevents the system from amplifying confident guessing on niche topics where all models share the same training gap. Requires `FIRECRAWL_API_KEY`. Falls back gracefully to standard disagreement synthesis without it.

### Module Map

```
src/moa/
├── cli.py        # Typer CLI (9 commands)
├── engine.py     # Core: adaptive routing, cascade, debate, review, deep research
├── models.py     # 14 models, 4 tiers, reviewer roles
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

### Design decisions (~$0.05-0.15, 8-15s)
```bash
moa ask "Redis vs Memcached for session storage in a Next.js app with 50K DAU?"
moa ask "Compare Drizzle ORM vs Prisma for a production Next.js app"
```

### Architecture review (~$0.15, 15-30s)
```bash
moa ask "Critique this architecture: Next.js → tRPC → PostgreSQL → Redis → S3. 
We expect 100K users in year one."
```

### Security review via pipe
```bash
cat src/auth/middleware.ts | moa ask --raw "Analyze this for security vulnerabilities"
git diff HEAD~3 | moa ask --raw "What are the riskiest changes in this diff?"
```

### Niche tooling questions (auto-researched)
```bash
moa ask "How do I configure Vercel Workflow DevKit for step-based execution?"
moa ask --research deep "What are the current best practices for LiteLLM fallback chains?"
```

### Multi-round debates (~$0.20-0.40, 30-60s)
```bash
moa debate "Is it better to use TypeScript strict mode from day one or add it incrementally?"
moa debate --rounds 3 "GraphQL gateway vs REST with BFF pattern?"
```

### Fact validation
```bash
moa ask "Is it true that React Server Components can't use useState? Verify with specifics."
moa ask "Does AWS Lambda still have a 15-minute timeout limit as of 2026?"
```

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

## Cost Reference

| Use Case | Mode | Cost | Latency |
|----------|------|------|---------|
| Quick question | adaptive:simple | ~$0.001 | 1-3s |
| Standard query | adaptive:standard | ~$0.05 | 8-15s |
| Complex decision | adaptive:complex | ~$0.15 | 15-30s |
| Deep research | --research deep | ~$0.15-0.30 | 30-60s |
| Code review | moa review | ~$0.10 | 15-25s |
| Debate (2 rounds) | moa debate | ~$0.20-0.40 | 30-60s |

Daily budget of $5.00 supports 100+ queries/day at typical usage.

## License

MIT

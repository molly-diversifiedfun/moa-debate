# moa-debate

Multi-model AI debate system using Mixture-of-Agents, Expert Panel, and Cascade patterns.

Runs queries through diverse AI models in parallel (GPT, Claude, Gemini, DeepSeek, Grok, Llama), synthesizes their responses, and auto-escalates to premium models only when confidence is low.

## Quick Start

```bash
# Install
cd ~/github/moa-debate
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Set API keys (core: Anthropic + OpenAI + Google)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
# GEMINI_API_KEY should already be set

# Optional bonus diversity
export DEEPSEEK_API_KEY=...
export XAI_API_KEY=...
export TOGETHER_API_KEY=...

# Check what's available
moa status
```

## Usage

```bash
# Cascade (recommended) — starts cheap, escalates if models disagree
moa ask --cascade "Explain the CAP theorem tradeoffs for Supabase"

# Direct tier selection
moa ask --tier lite "What's useMemo vs useCallback?"
moa ask --tier ultra "Should we shard or use read replicas?"

# Expert Panel code review (4 specialists: Security, Architecture, Performance, Correctness)
moa review --staged
git diff main..feature | moa review

# Multi-round debate
moa debate "Monorepo vs polyrepo for 4 brands?"

# HTTP server for n8n webhooks
moa serve --port 8787
```

## Architecture

**Cascade flow** (best quality/cost tradeoff):
1. **Lite pass** — 2 cheap proposers (4o-mini + Flash) → Sonnet synthesizes
2. **Haiku evaluates** — did models agree? Is this high-stakes?
3. **If confident** → done (~$0.05)
4. **If not** → **ultra pass** — 3 frontier models → Opus (~$0.30 total)

**4 tiers:**

| Tier | Core Proposers | Aggregator | ~Cost |
|---|---|---|---|
| flash | Gemini Flash | none | $0.001 |
| lite | 4o-mini, Flash (+optional) | Sonnet | $0.05 |
| pro | GPT-4.1, Gemini 2.5 Pro, Haiku (+optional) | Sonnet | $0.09 |
| ultra | GPT-5.4, Gemini 3.1 Pro, Sonnet (+optional) | Opus | $0.25 |

**14 models, 6 providers.** Core path runs on Anthropic + OpenAI + Google. DeepSeek, xAI, and Together/Meta are bonus diversity — automatically included when their keys are set.

## Claude Code Integration

```bash
# Slash commands (type in Claude Code)
/moa "question"           # Cascade multi-model query
/moa-review               # Expert Panel code review
/moa-debate "question"    # Multi-round debate

# The @reviewer agent auto-runs MoA Expert Panel
@reviewer review the changes
```

## API Server

```bash
moa serve --port 8787
```

Endpoints:
- `POST /moa` — `{"query": "...", "tier": "lite"}`
- `POST /cascade` — `{"query": "..."}`
- `POST /review` — `{"diff": "...", "context": "..."}`
- `POST /debate` — `{"query": "...", "rounds": 2}`
- `GET /health`

## License

MIT

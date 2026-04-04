# CLAUDE.md — moa-debate

## Overview
Multi-model AI debate system. Runs queries through diverse models in parallel (GPT, Claude, Gemini, DeepSeek, Grok, Llama), synthesizes results, auto-escalates to premium when confidence is low. Python CLI + HTTP API.

## Commands
```bash
pip install -e ".[dev]"                    # Install with dev deps
pytest                                      # Run all tests
pytest -v tests/test_engine.py             # Single file verbose

moa ask "<query>"                          # Adaptive routing (default)
moa ask --cascade "<query>"                # Legacy: lite → ultra if needed
moa ask --tier <flash|lite|pro|ultra> "<query>"  # Manual tier
moa ask --context . "<query>"              # Inject project context
moa ask --research deep "<query>"          # Multi-hop web research → single model
moa ask --research off "<query>"           # Disable auto-research on disagreement
moa review --staged                        # Expert panel code review
moa review < diff.patch                    # Review from stdin
moa debate "<question>" --rounds 3         # Multi-round debate
moa serve --port 8787                      # HTTP API server
moa verify                                 # Test model connectivity
moa status                                 # Roster + budget + API key status
moa history --last 20                      # Query history
moa history --cost                         # Spend summary
```

## Architecture

### Module Map
| Module | Purpose | Key abstractions |
|--------|---------|-----------------|
| `cli.py` | Typer CLI, 9 commands | `app = typer.Typer()` |
| `engine.py` | Core logic: adaptive routing, cascade, debate, review | `moa_query()`, `cascade_query()`, `debate()`, `expert_review()` |
| `models.py` | 14 models, 4 tiers, reviewer roles | `ModelConfig` dataclass, `Tier` dataclass, `ROSTER` dict |
| `server.py` | FastAPI HTTP API | 5 endpoints: `/moa`, `/cascade`, `/review`, `/debate`, `/health` |
| `config.py` | Constants: timeouts, budget, rate limits | `MAX_DAILY_SPEND_USD`, `MODEL_TIMEOUT_SECONDS` |
| `context.py` | Project context detection + injection | Auto-detects language, reads README/config, builds tree |
| `cache.py` | SQLite response caching | Key = SHA256(query:tier), TTL = 1 hour |
| `budget.py` | Daily spend cap + tracking | JSON file at `~/.moa/usage.json` |
| `history.py` | JSONL query logging | Appends to `~/.moa/history.jsonl` |
| `prompts.py` | System prompts for aggregation/debate/review | Template strings, not dynamic |
| `research.py` | Web search for grounding model responses | `SearchProvider` protocol, `FirecrawlProvider`, `lite_search()`, `deep_research()` |
| `verify.py` | Model connectivity test | Pings each model with tiny prompt |

### 4-Tier Model System
- **flash** (~$0.001) — Single Gemini Flash, no aggregation
- **lite** (~$0.05) — 2-5 cheap proposers → Sonnet aggregator
- **pro** (~$0.09) — 3-5 mid-tier proposers → Sonnet aggregator
- **ultra** (~$0.25) — 3-5 frontier proposers → Opus aggregator

### 4 Query Modes
1. **Adaptive Routing** (default) — Classifies query complexity → routes to minimal proposer set → detects consensus via Jaccard similarity (>35%). On disagreement, auto-searches web for reference material, re-asks with context.
2. **Deep Research** (`--research deep`) — Multi-hop web search (2-3 rounds via Firecrawl) → single frontier model synthesis. For questions needing grounding in docs.
3. **Cascade** (legacy) — Lite pass → Haiku evaluates confidence → escalates to ultra if low
4. **Debate** — Multi-round: independent responses → models see each other → revise → judge synthesizes

### Expert Panel Code Review
4 specialist reviewers with primary + fallback models:
- **Security** (GPT-4.1) — injection, auth, secrets, OWASP
- **Architecture** (Sonnet) — SOLID, coupling, async patterns
- **Performance** (Gemini 2.5 Pro) — complexity, N+1, memory
- **Correctness** (Gemini 3.1 Pro) — logic, edge cases, types

### State Files (all under ~/.moa/)
- `cache/cache.db` — SQLite response cache
- `usage.json` — daily spend tracking (per-day granularity)
- `history.jsonl` — query log
- `.env` — global fallback for API keys

### Key Design Patterns
- **Fallback chains** — every aggregator/reviewer has a fallback model
- **Provider semaphores** — per-provider concurrency limits (config.py)
- **Graceful degradation** — model failures return partial results, never crash
- **Immutable dataclasses** — ModelConfig, Tier, QueryCost are data, not behavior
- **Real cost tracking** — token counts from LiteLLM responses, not estimates
- **Research-augmented routing** — web search on model disagreement grounds responses in real docs

## 14 Models, 6 Providers
Core (need API keys): Anthropic (Opus, Sonnet, Haiku), OpenAI (GPT-5.4, GPT-4.1, 4o-mini), Google (Gemini 3.1 Pro, 2.5 Pro, Flash)
Optional: DeepSeek (V3, R1), xAI (Grok 4, 4.1-fast), Together/Meta (Llama-4-Maverick)

## Claude Code Integration
- `/moa "<question>"` — adaptive routing query
- `/moa-review` — expert panel on current changes
- `/moa-debate "<question>"` — multi-round debate
- `hooks/moa-review.sh` — PostToolUse hook that sends diffs to `/review` endpoint (requires `moa serve` running)

## Key Rules
- Prefer adaptive routing (default) over manual tier selection
- Cost-aware: flash for trivial, lite for most, ultra only for critical
- Never hardcode model names — use constants from `models.py` (e.g., `CLAUDE_SONNET`, `GPT_4_1`)
- Always handle model unavailability — check `model.available` before use
- Budget cap is $5/day by default — respect it in tests and new features
- Model names use LiteLLM format (e.g., `anthropic/claude-sonnet-4-20250514`, not raw provider names)

## Environment Variables
Required (at least one): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
Optional: `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `TOGETHER_API_KEY`
Research: `FIRECRAWL_API_KEY` — enables research-augmented routing (web search on disagreement + deep research mode)

## Testing
- Framework: pytest + pytest-asyncio
- Run: `pytest` (from project root)
- Test files: `tests/test_engine.py`, `tests/test_research.py`
- Coverage focus: model roster, tier definitions, reviewer roles, cost tracking, prompt formatting, research context formatting
- Set `GEMINI_API_KEY=test-key` in test env to allow imports without real keys
- Research tests use mock `SearchProvider` — no real API calls

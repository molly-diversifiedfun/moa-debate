# Configuration

Environment variables, state files, and the HTTP API server.

---

## Environment variables

All configuration via environment variables. No config files to manage.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic (Claude) API key |
| `OPENAI_API_KEY` | — | OpenAI (GPT) API key |
| `GEMINI_API_KEY` | — | Google (Gemini) API key |
| `DEEPSEEK_API_KEY` | — | DeepSeek (optional) |
| `XAI_API_KEY` | — | xAI / Grok (optional) |
| `TOGETHER_API_KEY` | — | Together.ai / Llama (optional) |
| `FIRECRAWL_API_KEY` | — | Firecrawl (web search). Optional — enables research |
| `MAX_DAILY_SPEND_USD` | 5.00 | Daily cost cap (0 = unlimited) |
| `MODEL_TIMEOUT_SECONDS` | 45 | Per-model call timeout |
| `CACHE_TTL_HOURS` | 1 | Response cache TTL |
| `MOA_SERVER_KEY` | — | API server auth key |

At minimum, set one of the three core providers (Anthropic, OpenAI, Google). More keys = more model diversity = better consensus signal.

### Loading order

1. Shell environment
2. Project `.env` file (in current working directory)
3. Global `~/.moa/.env` file (fallback)

Project `.env` overrides global. Global is useful for keys you always want available without per-project setup.

---

## State files

All persistent state lives under `~/.moa/`:

| File | Purpose |
|------|---------|
| `usage.json` | Daily spend tracking (per-day granularity) |
| `history.jsonl` | Query log — every `moa ask` call |
| `cache/cache.db` | SQLite response cache (1hr TTL) |
| `sessions/` | Session memory for contradiction detection |
| `health.json` | Circuit breaker state per model |
| `debates/` | Full debate transcripts for export |
| `outcomes.jsonl` | Outcome tracking (verdict → decision → result) |
| `templates/*.yaml` | Custom decision templates |
| `.env` | Global fallback for API keys |

---

## HTTP API

Run a local server that exposes the same functionality over HTTP:

```bash
moa serve --port 8787
```

### Endpoints

| Endpoint | Method | Body |
|----------|--------|------|
| `/moa` | POST | `{"query": "...", "tier": "lite"}` |
| `/cascade` | POST | `{"query": "..."}` |
| `/review` | POST | `{"diff": "...", "context": "..."}` |
| `/debate` | POST | `{"query": "...", "rounds": 2}` |
| `/health` | GET | — |

### Authentication

Set `MOA_SERVER_KEY` in the server environment. Clients must include it as a bearer token:

```bash
curl -X POST http://localhost:8787/moa \
  -H "Authorization: Bearer $MOA_SERVER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Should we use Redis?", "tier": "lite"}'
```

---

## Claude Code integration

MOA works as slash commands inside [Claude Code](https://claude.ai/code). Install the commands:

```bash
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

The slash command files live in `claude-code/` — customize them for your setup (update the path to your moa-debate venv).

# Model Safety Rules

## Never Hardcode Model Names
Use constants from `src/moa/models.py` (e.g., `CLAUDE_SONNET`, `GPT_4_1`, `GEMINI_FLASH`).
LiteLLM model identifiers change across versions — constants are the single source of truth.

## Always Handle Unavailability
Every model call path must handle the case where `model.available` is False.
Use the fallback chain pattern: primary model → fallback model → error with clear message.
Never assume an API key is set.

## Respect Tier Boundaries
- Don't use ultra-tier models in lite-tier flows
- Don't add Opus as a proposer in lite/pro tiers (it's an aggregator only)
- Reviewer roles have specific model assignments — don't swap without updating the role definition

## Cost Awareness
- New features that add model calls must document estimated cost impact
- Never remove or bypass the daily budget cap (`MAX_DAILY_SPEND_USD`)
- Test new flows with `--tier flash` first to validate logic cheaply
- Cache invalidation changes need extra scrutiny — breaking cache = multiplied API costs

## Provider Concurrency
Respect `PROVIDER_CONCURRENCY` limits in `config.py`. Adding new parallel calls to a provider
must account for the semaphore limit. DeepSeek has the lowest limit (3).

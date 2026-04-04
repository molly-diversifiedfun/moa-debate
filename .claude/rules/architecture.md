# Architecture Rules

## Module Boundaries
- `models.py` owns all model definitions and tier composition — never define models elsewhere
- `engine.py` owns query orchestration — CLI and server are thin wrappers that call engine functions
- `config.py` owns all constants — never hardcode timeouts, limits, or paths in other modules
- `prompts.py` owns all system prompts — don't inline prompt strings in engine.py

## Dataclass Immutability
`ModelConfig`, `Tier`, and `QueryCost` are dataclasses used as data, not behavior containers.
Don't add methods that mutate state. Create new instances instead.

## Fallback Chain Pattern
Every model selection must follow: primary → fallback → clear error.
```python
model = get_available(primary) or get_available(fallback)
if not model:
    raise ModelUnavailableError(f"Neither {primary.name} nor {fallback.name} available")
```

## State Files
All persistent state lives under `~/.moa/` (defined in `config.py`).
Never write state files to the project directory.
Always call `ensure_moa_home()` before accessing state files.

## LiteLLM is the Only Model Interface
All model calls go through `litellm.acompletion()`. Never call provider APIs directly.
This ensures consistent token counting, cost tracking, and timeout handling.

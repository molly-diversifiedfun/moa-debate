# Contributing to moa-debate

Thanks for your interest. Here's how to help.

## Before You Start

**File an issue first.** Before writing code, open an issue describing what you want to change and why. This prevents wasted work on things that don't fit the project direction.

## Development Setup

```bash
git clone https://github.com/molly-diversifiedfun/moa-debate.git
cd moa-debate
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Set at least one API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run tests
pytest                # 26 unit tests (no API calls)
moa test              # 5 live smoke tests (~$0.50)
moa verify            # Ping all models
```

## Making Changes

1. Create a branch: `git checkout -b feature/your-change`
2. Make your changes
3. Run tests: `pytest` (must all pass)
4. Run the smoke test: `moa test` (if you changed engine/CLI code)
5. Open a PR with a clear description of what and why

## What We're Looking For

**Good contributions:**
- Bug fixes with test cases
- New personas with clear philosophy descriptions (see `docs/PERSONAS.md` for the format)
- New SearchProvider implementations (Tavily, Serper, etc.)
- Performance improvements with benchmarks
- Documentation improvements

**Please don't:**
- Add features without discussing first
- Change the prompt templates without testing live results
- Add dependencies without justification
- Submit AI-generated PRs without reviewing them yourself

## Code Style

- Python 3.9+ compatible
- Type hints on function signatures
- Dataclasses for data, not behavior
- Immutable patterns — create new objects, don't mutate
- Constants in `config.py`, prompts in `prompts.py`, models in `models.py`
- Functions under 40 lines

## Adding a Persona

1. Add to `PERSONA_REGISTRY` in `src/moa/models.py`
2. Include: name, category, system_prompt, model, fallback
3. The system_prompt should capture their actual philosophy, not generic expertise
4. Add an entry to `docs/PERSONAS.md` with: philosophy, what they catch, key works with links
5. Test it: `moa ask --persona "Your Persona" "a relevant question"`

## Adding a Search Provider

1. Implement the `SearchProvider` protocol in `src/moa/research.py`
2. Add a factory function or extend `get_search_provider()`
3. Write tests with a mock provider (no real API calls in tests)
4. Update `.env.example` with the new API key

## Questions?

Open an issue. Keep it specific.

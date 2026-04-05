Run multi-model Expert Panel code review on the current changes.

Usage: /moa-review $ARGUMENTS

Sends the current git diff through specialized AI reviewers across different models, then synthesizes findings into a prioritized report with APPROVE / REQUEST CHANGES / BLOCK verdict.

Steps:
1. If $ARGUMENTS is empty, use `git diff --staged` to get staged changes
2. If $ARGUMENTS is a file path, read that diff file
3. If no staged changes, use `git diff HEAD~1` for the last commit
4. Run: `~/github/moa-debate/.venv/bin/moa review --staged` (or pipe the diff)
5. Display the full review including verdict
6. If Critical findings, highlight them prominently

Key flags (pass through if the user specifies):
- `--personas` — use famous engineer personas (Fowler, Beck, Hickey, Metz)
- `--persona "name,name"` — specific personas (e.g. "Rich Hickey,Sandi Metz")
- `--persona <category>` — all personas in a category: code, architecture
- `--discourse` — reviewers react to each other (AGREE/CHALLENGE/CONNECT/SURFACE)
- `--raw` — plain text output

Default review panel (4 specialists):
- **Security** (GPT-4.1): injection, auth, OWASP, secrets
- **Architecture** (Sonnet): SOLID, coupling, async patterns
- **Performance** (Gemini 2.5 Pro): Big-O, N+1, re-renders, bundle size
- **Correctness** (Gemini 3.1 Pro): off-by-one, edge cases, logic bugs

Persona options:
- code: Martin Fowler, Kent Beck, Rich Hickey, Sandi Metz
- architecture: Kelsey Hightower, Martin Kleppmann, DHH
- product: Shreya Doshi, Marty Cagan, April Dunford
- content: David Ogilvy, Ann Handley
- builder: Pieter Levels, Daniel Vassallo

When to recommend discourse mode:
- Large diffs with cross-cutting concerns (auth change that affects performance)
- When you want reviewers to challenge each other's findings (reduces false positives)

When to recommend personas over specialists:
- "Is this over-engineered?" → Rich Hickey
- "Where are the tests?" → Kent Beck
- "Does this class do too much?" → Sandi Metz
- "Could this be simpler?" → DHH

Examples:
- `/moa-review` — default expert panel on staged changes
- `/moa-review --personas` — Fowler/Beck/Hickey/Metz review
- `/moa-review --persona "Rich Hickey" --discourse` — Hickey + cross-reviewer discourse
- `/moa-review --persona architecture` — Hightower/Kleppmann/DHH
- `cat src/auth.py | /moa-review` — review a specific file

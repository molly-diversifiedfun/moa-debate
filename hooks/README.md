# Git Hooks

Tracked git hooks for moa-debate. Live in `hooks/` so they're committed with
the repo, and get symlinked into `.git/hooks/` by the install script.

## Install

```bash
./hooks/install.sh
```

This is idempotent — safe to run on a fresh clone or to re-link after edits.

## Hooks

| Hook | Trigger | What it does | Time |
|---|---|---|---|
| `pre-commit` | `git commit` | If `src/moa/cli.py` is staged, verifies it imports cleanly via `python3 -c "from moa.cli import app"`. Catches missing imports, syntax errors, name shadowing — the failure mode behind the Session 4 missing-Optional bug and Session 5 `UnboundLocalError`. | ~1s |
| `pre-push` | `git push` | Runs the full `pytest -q` suite (197 mock tests). Blocks the push if anything fails. | ~7s |

## Bypass

```bash
git commit --no-verify   # skip pre-commit
git push --no-verify     # skip pre-push
```

Use sparingly — these checks are cheap and exist because we've already shipped
the bugs they catch.

## Editing

Edit the files in `hooks/` (not `.git/hooks/`). Because they're symlinked, your
changes take effect immediately. Commit and push so other clones pick them up.

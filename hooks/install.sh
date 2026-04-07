#!/bin/sh
# Install moa-debate git hooks.
# Symlinks files from hooks/ → .git/hooks/ so updates flow automatically.
#
# Usage: ./hooks/install.sh

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOKS_SRC="$REPO_ROOT/hooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_SRC" ]; then
  echo "❌ hooks/ directory not found at $HOOKS_SRC"
  exit 1
fi

mkdir -p "$HOOKS_DST"

installed=0
for hook in pre-commit pre-push; do
  src="$HOOKS_SRC/$hook"
  dst="$HOOKS_DST/$hook"

  if [ ! -f "$src" ]; then
    continue
  fi

  # Remove any existing hook (file or symlink) to keep installs idempotent.
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    rm -f "$dst"
  fi

  ln -s "../../hooks/$hook" "$dst"
  chmod +x "$src"
  echo "✅ installed: $hook → $dst"
  installed=$((installed + 1))
done

if [ "$installed" -eq 0 ]; then
  echo "⚠️  No hooks installed (nothing in $HOOKS_SRC)"
  exit 1
fi

echo ""
echo "Installed $installed hook(s). They will run automatically on commit/push."
echo "Bypass when needed with: git commit --no-verify  /  git push --no-verify"

#!/bin/bash
# moa-review.sh — Claude Code PostToolUse hook (matcher: Edit|Write)
# Sends the diff of changed files to the MoA Expert Panel for automated code review.
# Wire this in settings.json under PostToolUse with matcher "Edit|Write".

# Read the hook input from stdin
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)

# Skip non-code files
case "$FILE_PATH" in
  *.md|*.txt|*.json|*.yml|*.yaml|*.env*|*.lock|*.log)
    exit 0
    ;;
esac

# Only review if the file exists and has a git diff
if [ -n "$FILE_PATH" ] && [ -f "$FILE_PATH" ]; then
  DIFF=$(git diff -- "$FILE_PATH" 2>/dev/null)
  if [ -n "$DIFF" ]; then
    # Send to MoA review endpoint (non-blocking, timeout after 30s)
    RESULT=$(curl -s --max-time 30 \
      -X POST http://127.0.0.1:8787/review \
      -H "Content-Type: application/json" \
      -d "{\"diff\": $(echo "$DIFF" | jq -Rs .), \"context\": \"File: $FILE_PATH\"}" \
      2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$RESULT" ]; then
      RESPONSE=$(echo "$RESULT" | jq -r '.response // empty' 2>/dev/null)
      if [ -n "$RESPONSE" ]; then
        echo "🔍 MoA Review for $FILE_PATH:" >&2
        echo "$RESPONSE" >&2
      fi
    fi
  fi
fi

exit 0

#!/usr/bin/env bash
# harbor SessionStart hook — inject one-line registry summary.
# Budget: <100 tokens injected to context.

set -u

REGISTRY_DIR="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/harbor}/mcp/harbor/data"
BENCH_FILE="$REGISTRY_DIR/benchmarks.yaml"

count_entries() {
    local f="$1"
    [ -f "$f" ] || { echo 0; return; }
    local n
    n=$(grep -c '^[[:space:]]*status:[[:space:]]*verified[[:space:]]*$' "$f" 2>/dev/null) || n=0
    echo "${n:-0}"
}

BENCH_COUNT=$(count_entries "$BENCH_FILE")

if [ -f "$BENCH_FILE" ]; then
    LAST_UPDATE=$(stat -c %y "$BENCH_FILE" 2>/dev/null | cut -d' ' -f1)
    LAST_UPDATE="${LAST_UPDATE:-unknown}"
else
    LAST_UPDATE="unknown"
fi

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "[harbor] benchmarks=$BENCH_COUNT verified | last update=$LAST_UPDATE\nTools: /harbor (full surface), /benchmark. Heavy work via Skill('env-generator')."
  }
}
EOF

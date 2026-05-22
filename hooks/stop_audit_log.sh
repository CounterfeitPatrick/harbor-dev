#!/usr/bin/env bash
# harbor Stop / SubagentStop hook — append per-turn audit record to disk.
# Budget: <1 second.

set -u

INPUT=$(cat)
LOG_DIR="$HOME/.claude/audit"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).jsonl"

if command -v jq >/dev/null 2>&1; then
    echo "$INPUT" | jq -c '{
        ts: now,
        session_id: (.session_id // ""),
        agent: (.agent // ""),
        stop_hook_active: (.stop_hook_active // false),
        transcript_path: (.transcript_path // "")
    }' >> "$LOG_FILE" 2>/dev/null || true
else
    echo "{\"ts\": $(date +%s), \"raw\": $(echo "$INPUT" | head -c 1000 | tr -d '\n' | sed 's/"/\\"/g')}" >> "$LOG_FILE" 2>/dev/null || true
fi

echo '{"continue": true}'

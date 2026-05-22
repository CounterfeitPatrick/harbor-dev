#!/usr/bin/env bash
# harbor PostToolUse hook — truncate long Bash outputs from heavy commands.
# Triggered on Bash with command matching docker build|compose / pytest / run_eval / run_demo.
# Folds >200-line outputs into HEAD/ERRORS/TAIL slices.
# Budget: <2 seconds.

set -u

INPUT=$(cat)

if ! command -v jq >/dev/null 2>&1; then
    echo '{"continue": true}'
    exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
if [[ ! "$CMD" =~ (docker[[:space:]]+(build|compose)|pytest|run_eval|run_demo) ]]; then
    echo '{"continue": true}'
    exit 0
fi

OUTPUT=$(echo "$INPUT" | jq -r '(.tool_response.stdout // "") + (.tool_response.stderr // "")')
LINE_COUNT=$(echo "$OUTPUT" | wc -l)

if [ "$LINE_COUNT" -le 200 ]; then
    echo '{"continue": true}'
    exit 0
fi

HEAD=$(echo "$OUTPUT" | head -50)
TAIL=$(echo "$OUTPUT" | tail -50)
ERRORS=$(echo "$OUTPUT" | grep -iE "error|fail|traceback|fatal" | head -20)

jq -n \
    --arg head "$HEAD" \
    --arg tail "$TAIL" \
    --arg err "$ERRORS" \
    --arg total "$LINE_COUNT" \
    '{
        decision: "block",
        reason: ("[harbor truncate] " + $total + " lines folded\n=== HEAD ===\n" + $head + "\n=== ERRORS ===\n" + $err + "\n=== TAIL ===\n" + $tail)
    }'

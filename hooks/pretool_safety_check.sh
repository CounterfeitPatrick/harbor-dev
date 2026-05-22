#!/usr/bin/env bash
# harbor PreToolUse hook for the Bash tool.
# Refuses obviously-destructive commands; harbor runs docker / pytest a lot,
# so this catches accidents before they reach the shell.
#
# Contract:
#   stdin  -> JSON payload of the tool_use call (Claude Code passes this)
#   stdout -> decision JSON (only when blocking)
#   exit 0 -> allow (silent)
#   exit 2 -> block (Claude Code reads stdout JSON for the reason)

set -euo pipefail

input=$(cat)

cmd=$(echo "$input" | python3 -c '
import json, sys
try:
    payload = json.load(sys.stdin)
    print(payload.get("tool_input", {}).get("command", ""))
except Exception:
    pass
' 2>/dev/null || true)

if [[ -z "$cmd" ]]; then
    cmd=$(echo "$input" | grep -oE '"command"\s*:\s*"[^"]*"' | head -n1 | sed 's/.*"command"\s*:\s*"\(.*\)"/\1/' || true)
fi

declare -a DANGEROUS_PATTERNS=(
    'rm[[:space:]]+-rf?[[:space:]]+/($|[[:space:]])'         # rm -rf /
    'rm[[:space:]]+-rf?[[:space:]]+~($|[[:space:]])'         # rm -rf ~
    ':\(\)\{[[:space:]]*:\|:&[[:space:]]*\};:'                # fork bomb
    'mkfs\.[a-z]+[[:space:]]+/dev/'                          # mkfs on device
    'dd[[:space:]]+.*of=/dev/sd'                             # raw write to disk
    '>[[:space:]]*/dev/sd[a-z]'                              # stdout to disk
    'docker[[:space:]]+system[[:space:]]+prune[[:space:]]+.*--volumes.*-f'   # nuke all volumes incl. registry
    'docker[[:space:]]+volume[[:space:]]+prune[[:space:]]+.*-f'              # delete all volumes
)

for pat in "${DANGEROUS_PATTERNS[@]}"; do
    if [[ "$cmd" =~ $pat ]]; then
        cat <<EOF
{"decision":"block","reason":"harbor PreToolUse hook: refusing dangerous pattern '$pat'. If you really mean it, run from a shell outside Claude Code."}
EOF
        exit 2
    fi
done

exit 0

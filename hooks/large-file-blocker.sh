#!/usr/bin/env bash
# large-file-blocker.sh — Block commits containing files over a size threshold.
#
# PreToolUse hook for Bash (git commit commands).
# Checks staged files for anything exceeding the size limit.
# Prevents accidental commits of build artifacts, database dumps, or media.
#
# Receives Bash tool input as JSON on stdin.
# Exit 0 = allow, exit 2 = block.

MAX_SIZE_KB=5120  # 5 MB

INPUT=$(cat)

COMMAND=$(echo "${INPUT}" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('input', {}).get('command', ''))
except Exception:
    pass
" 2>/dev/null)

# Only check git commit commands
if ! echo "${COMMAND}" | grep -qE '\bgit\s+commit\b'; then
    exit 0
fi

# Get staged files with their sizes
LARGE_FILES=""
while IFS= read -r file; do
    [[ -z "${file}" ]] && continue
    [[ ! -f "${file}" ]] && continue

    SIZE_KB=$(du -k "${file}" 2>/dev/null | cut -f1) || true
    if [[ -n "${SIZE_KB}" ]] && [[ "${SIZE_KB}" -gt "${MAX_SIZE_KB}" ]]; then
        SIZE_MB=$(awk "BEGIN {printf \"%.1f\", ${SIZE_KB} / 1024}" 2>/dev/null || echo "${SIZE_KB}KB")
        LARGE_FILES="${LARGE_FILES}\n  ${file} (${SIZE_MB} MB)"
    fi
done < <(git diff --cached --name-only 2>/dev/null || true)

if [[ -n "${LARGE_FILES}" ]]; then
    echo "BLOCKED: Staged files exceed ${MAX_SIZE_KB}KB size limit."
    echo -e "${LARGE_FILES}"
    echo ""
    echo "Remove large files from staging with: git reset HEAD <file>"
    echo "Consider using .gitignore or Git LFS for large files."
    exit 2
fi

exit 0

#!/usr/bin/env bash
# Scan written/edited files for common AI-generated code patterns (slop).
#
# Outputs warnings to stderr for the model to self-correct.
# Never blocks (always exits 0). Only flags high-confidence patterns.
#
# Receives Edit/Write tool input as JSON on stdin.

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "${INPUT}" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('input', {}).get('file_path', ''))
except:
    pass
" 2>/dev/null)

if [[ -z "${FILE_PATH}" ]] || [[ ! -f "${FILE_PATH}" ]]; then
    exit 0
fi

EXT="${FILE_PATH##*.}"

# Skip hook files (they contain detection patterns that look like slop)
case "${FILE_PATH}" in
    */hooks/*) exit 0 ;;
esac

# Only check code files
case "${EXT}" in
    js|jsx|ts|tsx|py|go|rs|rb|java|kt|swift|sh|bash|zsh) ;;
    *) exit 0 ;;
esac

WARNINGS=""
LINE_NUM=0

while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))

    # Filler comments: "This function/method/class ..."
    if echo "${line}" | grep -qE '^\s*(//|#|/\*)\s*This (function|method|class|module|component|hook|helper) '; then
        WARNINGS="${WARNINGS}  line ${LINE_NUM}: narration comment ('This function/method/class...')\n"
    fi

    # console.log left as debug artifact (not in test files)
    if [[ "${FILE_PATH}" != *test* ]] && [[ "${FILE_PATH}" != *spec* ]]; then
        if echo "${line}" | grep -qE '^\s*console\.(log|debug)\('; then
            WARNINGS="${WARNINGS}  line ${LINE_NUM}: console.log/debug left in production code\n"
        fi
    fi

    # Empty catch blocks
    if echo "${line}" | grep -qE 'catch\s*(\([^)]*\))?\s*\{\s*\}'; then
        WARNINGS="${WARNINGS}  line ${LINE_NUM}: empty catch block swallows errors\n"
    fi

    # TODO/FIXME without context (just "TODO" or "TODO: fix" with no detail)
    if echo "${line}" | grep -qE '(TODO|FIXME)(:?\s*$|:\s*(fix|do|handle|add|implement|update)\s*(this|it|later)?\s*$)'; then
        WARNINGS="${WARNINGS}  line ${LINE_NUM}: TODO/FIXME without actionable context\n"
    fi

    # Boolean comparison to literal: === true, === false, == true, == false
    if echo "${line}" | grep -qE '===?\s*(true|false)\b'; then
        WARNINGS="${WARNINGS}  line ${LINE_NUM}: unnecessary boolean literal comparison\n"
    fi

    # Unnecessary ternary returning boolean: x ? true : false
    if echo "${line}" | grep -qE '\?\s*true\s*:\s*false'; then
        WARNINGS="${WARNINGS}  line ${LINE_NUM}: ternary returning boolean literal (use the condition directly)\n"
    fi

done < "${FILE_PATH}"

if [[ -n "${WARNINGS}" ]]; then
    echo "DESLOP: AI-pattern warnings in ${FILE_PATH}:" >&2
    echo -e "${WARNINGS}" >&2
    echo "These are suggestions, not blockers. Review and fix if appropriate." >&2
fi

exit 0

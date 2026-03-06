#!/usr/bin/env bash
# Auto-format files after Edit/Write operations based on file extension.
#
# Runs the appropriate formatter silently. If the formatter is not
# installed, does nothing. Never fails or blocks.
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

format_with() {
    if command -v "$1" >/dev/null 2>&1; then
        "$@" >/dev/null 2>&1 || true
    fi
}

case "${EXT}" in
    js|jsx|ts|tsx|json|css|scss|html|md|yaml|yml)
        format_with prettier --write "${FILE_PATH}"
        ;;
    py)
        if command -v black >/dev/null 2>&1; then
            black --quiet "${FILE_PATH}" >/dev/null 2>&1 || true
        elif command -v ruff >/dev/null 2>&1; then
            ruff format "${FILE_PATH}" >/dev/null 2>&1 || true
        fi
        ;;
    go)
        format_with gofmt -w "${FILE_PATH}"
        ;;
    rs)
        format_with rustfmt "${FILE_PATH}"
        ;;
    rb)
        format_with rubocop -A --fail-level E "${FILE_PATH}"
        ;;
    sh|bash|zsh)
        format_with shfmt -w "${FILE_PATH}"
        ;;
    *) ;;
esac

exit 0

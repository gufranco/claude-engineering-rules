#!/usr/bin/env bash
# Accumulate edited paths during the response. Batch-format at Stop.
#
# Previous behavior: format the file immediately after each Edit/Write.
# On a 10-file refactor that meant 10 separate formatter invocations and
# 10 separate tsc / typecheck passes when the type-check follower hook ran.
#
# New behavior: this script appends edited paths to a per-session batch
# file. The Stop-event companion script (stop-format-typecheck.sh) reads
# the file once, deduplicates, formats everything, runs typecheck once,
# clears the batch file.
#
# Receives Edit/Write tool input as JSON on stdin.

set -euo pipefail

# Surface unexpected aborts instead of failing silently.
trap 'echo "smart-formatter: hook aborted at line ${LINENO}" >&2' ERR

# Profile gate. Skip when the profile excludes this hook or it is in the
# CLAUDE_DISABLED_HOOKS list. The Python helper is the source of truth.
if ! python3 -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
try:
    from _lib.hook_profile import should_run
    sys.exit(0 if should_run('smart-formatter') else 1)
except Exception:
    sys.exit(0)
" 2>/dev/null; then
    exit 0
fi

INPUT=$(cat)

FILE_PATH=$(echo "${INPUT}" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', data.get('input', {})).get('file_path', ''))
except:
    pass
" 2>/dev/null || true)

if [[ -z "${FILE_PATH}" ]] || [[ ! -f "${FILE_PATH}" ]]; then
    exit 0
fi

# Skip the dot-everything: cache files, lock files, generated artifacts.
case "${FILE_PATH}" in
    */.claude/cache/*|*/node_modules/*|*/.git/*|*/dist/*|*/build/*) exit 0 ;;
esac

BATCH_DIR="${HOME}/.claude/cache"
BATCH_FILE="${BATCH_DIR}/edit-batch.txt"

mkdir -p "${BATCH_DIR}"
# Append the path and flush. The Stop hook will dedupe.
echo "${FILE_PATH}" >> "${BATCH_FILE}"

exit 0

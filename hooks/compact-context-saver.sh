#!/usr/bin/env bash
# compact-context-saver.sh — Preserve and restore context across compaction.
#
# Usage:
#   PreCompact:  saves git status and branch to ~/.claude/.compact-context
#   PostCompact: reads the saved file and outputs it as a context reminder
#
# Pass "pre" or "post" as the first argument, or detect from hook type.

set -euo pipefail

CONTEXT_FILE="${HOME}/.claude/.compact-context"

save_context() {
    mkdir -p "$(dirname "${CONTEXT_FILE}")"
    {
        echo "=== Compact Context Snapshot ==="
        echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S GMT')"
        echo "Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
        echo ""
        echo "Modified files:"
        git status --porcelain 2>/dev/null || echo "  not a git repo"
    } > "${CONTEXT_FILE}"
}

restore_context() {
    if [[ -f "${CONTEXT_FILE}" ]]; then
        echo "Context preserved before compaction:"
        cat "${CONTEXT_FILE}"
    fi
}

case "${1:-pre}" in
    pre)  save_context ;;
    post) restore_context ;;
    *)    echo "Usage: $0 [pre|post]" >&2; exit 1 ;;
esac

exit 0

#!/usr/bin/env bash
# Read the batched edit list, dedupe, format every file once, run
# typecheck once across the touched workspaces. Clear the batch.
#
# Runs at Stop. Pairs with smart-formatter.sh (PostToolUse accumulator).

set -euo pipefail

trap 'echo "stop-format-typecheck: hook aborted at line ${LINENO}" >&2' ERR

# Profile gate
if ! python3 -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
try:
    from _lib.profile import should_run
    sys.exit(0 if should_run('stop-format-typecheck') else 1)
except Exception:
    sys.exit(0)
" 2>/dev/null; then
    exit 0
fi

BATCH_FILE="${HOME}/.claude/cache/edit-batch.txt"
if [[ ! -s "${BATCH_FILE}" ]]; then
    exit 0
fi

# Deduplicate and read into an array.
mapfile -t FILES < <(sort -u "${BATCH_FILE}" | grep -v '^$' || true)

if [[ ${#FILES[@]} -eq 0 ]]; then
    : > "${BATCH_FILE}"
    exit 0
fi

format_with() {
    if command -v "$1" >/dev/null 2>&1; then
        "$@" >/dev/null 2>&1 || true
    fi
}

# Group by extension to call each formatter once with all relevant files.
declare -a PRETTIER_FILES=()
declare -a PYTHON_FILES=()
declare -a GO_FILES=()
declare -a RUST_FILES=()
declare -a RUBY_FILES=()
declare -a SHELL_FILES=()

for f in "${FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        continue
    fi
    case "${f##*.}" in
        js|jsx|ts|tsx|json|css|scss|html|md|yaml|yml)
            PRETTIER_FILES+=("$f")
            ;;
        py)
            PYTHON_FILES+=("$f")
            ;;
        go)
            GO_FILES+=("$f")
            ;;
        rs)
            RUST_FILES+=("$f")
            ;;
        rb)
            RUBY_FILES+=("$f")
            ;;
        sh|bash|zsh)
            SHELL_FILES+=("$f")
            ;;
    esac
done

# Run each formatter once with all relevant files as arguments.
if [[ ${#PRETTIER_FILES[@]} -gt 0 ]]; then
    format_with prettier --write "${PRETTIER_FILES[@]}"
fi
if [[ ${#PYTHON_FILES[@]} -gt 0 ]]; then
    if command -v black >/dev/null 2>&1; then
        black --quiet "${PYTHON_FILES[@]}" >/dev/null 2>&1 || true
    elif command -v ruff >/dev/null 2>&1; then
        ruff format "${PYTHON_FILES[@]}" >/dev/null 2>&1 || true
    fi
fi
if [[ ${#GO_FILES[@]} -gt 0 ]]; then
    format_with gofmt -w "${GO_FILES[@]}"
fi
if [[ ${#RUST_FILES[@]} -gt 0 ]]; then
    for f in "${RUST_FILES[@]}"; do
        format_with rustfmt "$f"
    done
fi
if [[ ${#RUBY_FILES[@]} -gt 0 ]]; then
    format_with rubocop -A --fail-level E "${RUBY_FILES[@]}"
fi
if [[ ${#SHELL_FILES[@]} -gt 0 ]]; then
    format_with shfmt -w "${SHELL_FILES[@]}"
fi

# One typecheck pass per workspace root, not per file.
# Find the nearest workspace root (with package.json + tsconfig.json) for
# any of the TypeScript files.
declare -A TS_WORKSPACES=()
for f in "${PRETTIER_FILES[@]}"; do
    case "${f##*.}" in
        ts|tsx)
            dir=$(dirname "$f")
            while [[ "$dir" != "/" ]]; do
                if [[ -f "$dir/tsconfig.json" ]] && [[ -f "$dir/package.json" ]]; then
                    TS_WORKSPACES["$dir"]=1
                    break
                fi
                dir=$(dirname "$dir")
            done
            ;;
    esac
done

for ws in "${!TS_WORKSPACES[@]}"; do
    if [[ -d "$ws" ]]; then
        # Use the project's incremental TypeScript checker if available.
        (cd "$ws" && timeout 60 npx --no-install tsc --noEmit --incremental --tsBuildInfoFile node_modules/.cache/tsc-hook.tsbuildinfo >/dev/null 2>&1) || true
    fi
done

# Clear the batch file.
: > "${BATCH_FILE}"

exit 0

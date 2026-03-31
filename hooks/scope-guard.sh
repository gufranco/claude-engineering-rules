#!/usr/bin/env bash
# scope-guard.sh — Detect files modified outside declared scope.
#
# Two modes:
# 1. Spec-based: compares git-modified files against a .spec.md file.
# 2. Freeze mode: when ~/.claude/.freeze-scope exists, blocks all edits
#    outside the frozen directory. Used by /investigate --freeze.
#
# Non-blocking in spec mode (warning only).
# Blocking in freeze mode (exits non-zero to prevent edits).
# Install per-project by adding to .claude/settings.json.

FREEZE_FILE="${HOME}/.claude/.freeze-scope"

# ── Freeze mode check ──────────────────────────────────────────────
# Read tool input from stdin (PreToolUse hooks receive JSON on stdin)
STDIN_INPUT=$(cat 2>/dev/null || true)

if [[ -f "${FREEZE_FILE}" ]]; then
  FROZEN_DIR=$(cat "${FREEZE_FILE}" 2>/dev/null)
  if [[ -n "${FROZEN_DIR}" ]]; then
    # Extract file_path from the tool input JSON
    INPUT_FILE=""
    if [[ -n "${STDIN_INPUT}" ]]; then
      INPUT_FILE=$(echo "${STDIN_INPUT}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('input',{}).get('file_path',''))" 2>/dev/null || true)
    fi

    if [[ -n "${INPUT_FILE}" ]]; then
      # Resolve to absolute path for comparison
      RESOLVED_INPUT=$(cd "$(dirname "${INPUT_FILE}" 2>/dev/null)" && pwd)/$(basename "${INPUT_FILE}") 2>/dev/null || INPUT_FILE
      RESOLVED_FROZEN=$(cd "${FROZEN_DIR}" 2>/dev/null && pwd) 2>/dev/null || FROZEN_DIR

      case "${RESOLVED_INPUT}" in
        "${RESOLVED_FROZEN}"/*) ;; # Inside frozen scope, allow
        *)
          echo ""
          echo "FREEZE GUARD: Edit blocked. Scope is frozen to: ${FROZEN_DIR}"
          echo "  Attempted edit: ${INPUT_FILE}"
          echo "  Run /investigate --unfreeze to remove the restriction."
          echo ""
          exit 2
          ;;
      esac
    fi
  fi
fi

# ── Spec-based scope check ─────────────────────────────────────────
PROJECT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")

# Find the most recent .spec.md file
SPEC_FILE=""
SPEC_FILE=$(find "${PROJECT_DIR}" -name "*.spec.md" -type f -print 2>/dev/null | sort -r | head -1) || true
[[ -z "${SPEC_FILE}" ]] && exit 0

# Extract declared files from "Files to Create/Modify" section
# Backticks are intentional: matching literal markdown syntax
DECLARED=""
# shellcheck disable=SC2016
DECLARED=$(sed -n '/^##.*[Ff]iles.*[Cc]reate\|^##.*[Ff]iles.*[Mm]odify/,/^##/p' "${SPEC_FILE}" 2>/dev/null \
  | grep -oE '`[^`]+`' \
  | tr -d '`' \
  | sort -u) || true

[[ -z "${DECLARED}" ]] && exit 0

# Get files actually modified (staged + unstaged)
MODIFIED=""
MODIFIED=$(git diff --name-only HEAD 2>/dev/null | sort -u) || true
[[ -z "${MODIFIED}" ]] && exit 0

# Patterns to always exclude from scope warnings
EXCLUDED_PATTERN="(test|spec|__tests__|fixture|mock|stub|\.config\.|package-lock|yarn\.lock|pnpm-lock|\.md$|\.txt$)"

OUT_OF_SCOPE=""
while IFS= read -r file; do
  # Skip excluded patterns
  echo "${file}" | grep -qE "${EXCLUDED_PATTERN}" && continue

  # Check if file is in declared scope
  FOUND=0
  while IFS= read -r declared; do
    [[ -z "${declared}" ]] && continue
    case "${file}" in *"${declared}"*) FOUND=1; break ;; *) ;; esac
  done <<< "${DECLARED}"

  [[ "${FOUND}" -eq 0 ]] && OUT_OF_SCOPE="${OUT_OF_SCOPE}\n  - ${file}"
done <<< "${MODIFIED}"

if [[ -n "${OUT_OF_SCOPE}" ]]; then
  echo ""
  echo "SCOPE GUARD: Files modified outside declared spec scope (${SPEC_FILE}):"
  echo -e "${OUT_OF_SCOPE}"
  echo ""
  echo "  This may indicate scope creep. Review before committing."
  echo ""
fi

exit 0

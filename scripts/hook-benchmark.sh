#!/usr/bin/env bash
# hook-benchmark.sh — Measure execution time of each hook against a safe fixture.
#
# Usage:
#   bash scripts/hook-benchmark.sh
#   bash scripts/hook-benchmark.sh --threshold 500  # fail if any hook exceeds 500ms
#
# Hooks must complete in under 500ms to avoid blocking Claude's response.

set -euo pipefail

HOOKS_DIR="$(dirname "$0")/../hooks"
FIXTURES_DIR="$(dirname "$0")/../tests/fixtures"
THRESHOLD_MS="${2:-500}"
SAFE_FIXTURE="${FIXTURES_DIR}/bash-safe-command.json"
WRITE_FIXTURE="${FIXTURES_DIR}/write-typescript-file.json"
EDIT_FIXTURE="${FIXTURES_DIR}/edit-nonexistent-file.json"

PASS=0
FAIL=0

measure_hook() {
  local hook="$1"
  local fixture="$2"
  local label="$3"

  if [[ ! -f "${hook}" ]]; then
    echo "SKIP (missing): ${label}"
    return
  fi

  if [[ ! -f "${fixture}" ]]; then
    echo "SKIP (no fixture): ${label}"
    return
  fi

  local start end elapsed

  start=$(date +%s%3N)
  cat "${fixture}" | timeout 5 bash "${hook}" >/dev/null 2>&1 || true
  end=$(date +%s%3N)
  elapsed=$(( end - start ))

  if [[ "${elapsed}" -le "${THRESHOLD_MS}" ]]; then
    printf "PASS (%4dms): %s\n" "${elapsed}" "${label}"
    (( PASS++ )) || true
  else
    printf "FAIL (%4dms > %dms threshold): %s\n" "${elapsed}" "${THRESHOLD_MS}" "${label}"
    (( FAIL++ )) || true
  fi
}

echo "=== Hook Benchmark (threshold: ${THRESHOLD_MS}ms) ==="
echo ""

measure_hook "${HOOKS_DIR}/dangerous-command-blocker.py"  "${SAFE_FIXTURE}"    "dangerous-command-blocker (safe bash)"
measure_hook "${HOOKS_DIR}/secret-scanner.py"             "${SAFE_FIXTURE}"    "secret-scanner (safe bash)"
measure_hook "${HOOKS_DIR}/conventional-commits.sh"       "${FIXTURES_DIR}/commit-valid.json" "conventional-commits (valid)"
measure_hook "${HOOKS_DIR}/gh-token-guard.py"             "${FIXTURES_DIR}/bash-gh-with-token.json" "gh-token-guard (with token)"
measure_hook "${HOOKS_DIR}/glab-token-guard.py"           "${FIXTURES_DIR}/bash-glab-with-token.json" "glab-token-guard (with token)"
measure_hook "${HOOKS_DIR}/large-file-blocker.sh"         "${SAFE_FIXTURE}"    "large-file-blocker (safe bash)"
measure_hook "${HOOKS_DIR}/env-file-guard.sh"             "${WRITE_FIXTURE}"   "env-file-guard (typescript file)"
measure_hook "${HOOKS_DIR}/smart-formatter.sh"            "${WRITE_FIXTURE}"   "smart-formatter (typescript file)"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed (threshold: ${THRESHOLD_MS}ms)"

[[ "${FAIL}" -eq 0 ]] || exit 1

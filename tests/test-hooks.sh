#!/usr/bin/env bash
# test-hooks.sh — Smoke tests for Claude Code hooks.
#
# Feeds JSON fixtures to each hook and verifies exit codes.
# Exit 0 = all tests pass, exit 1 = at least one failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES="${SCRIPT_DIR}/fixtures"
HOOKS="${SCRIPT_DIR}/../hooks"
PASS=0
FAIL=0

run_test() {
    local description="$1"
    local hook="$2"
    local fixture="$3"
    local expected_exit="$4"

    local actual_exit=0
    "${hook}" < "${fixture}" >/dev/null 2>&1 || actual_exit=$?

    if [[ "${actual_exit}" -eq "${expected_exit}" ]]; then
        echo "  PASS: ${description} (exit ${actual_exit})"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: ${description} (expected exit ${expected_exit}, got ${actual_exit})"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "=== Dangerous Command Blocker ==="

run_test "allows safe commands" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-safe-command.json" 0

run_test "blocks rm -rf /" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-catastrophic-rm.json" 2

run_test "blocks git push --force" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-force-push.json" 2

run_test "blocks curl pipe to shell" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-pipe-to-shell.json" 2

run_test "blocks rm -rf .git" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-delete-git.json" 2

run_test "blocks git reset --hard" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-git-reset-hard.json" 2

run_test "blocks fork bomb" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-fork-bomb.json" 2

echo ""
echo "=== Conventional Commits ==="

run_test "allows valid conventional commit" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/commit-valid.json" 0

run_test "blocks non-conventional commit message" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/commit-invalid.json" 2

run_test "ignores non-commit commands" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/commit-not-a-commit.json" 0

echo ""
echo "=== Secret Scanner ==="

run_test "ignores non-commit commands" \
    "${HOOKS}/secret-scanner.py" \
    "${FIXTURES}/commit-not-a-commit.json" 0

run_test "allows safe commands" \
    "${HOOKS}/secret-scanner.py" \
    "${FIXTURES}/bash-safe-command.json" 0

echo ""
echo "=== Smart Formatter ==="

run_test "handles nonexistent file gracefully" \
    "${HOOKS}/smart-formatter.sh" \
    "${FIXTURES}/edit-nonexistent-file.json" 0

echo ""
echo "=== Change Tracker ==="

run_test "handles nonexistent file gracefully" \
    "${HOOKS}/change-tracker.sh" \
    "${FIXTURES}/write-tool-input.json" 0

echo ""
echo "=== Results ==="
echo "  Passed: ${PASS}"
echo "  Failed: ${FAIL}"
echo ""

if [[ "${FAIL}" -gt 0 ]]; then
    exit 1
fi

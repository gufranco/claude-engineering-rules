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

run_test "blocks commit with subject over 72 chars" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/bash-commit-long-subject.json" 2

run_test "allows valid heredoc commit" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/bash-commit-heredoc.json" 0

echo ""
echo "=== Secret Scanner ==="

run_test "ignores non-commit commands" \
    "${HOOKS}/secret-scanner.py" \
    "${FIXTURES}/commit-not-a-commit.json" 0

run_test "allows safe commands" \
    "${HOOKS}/secret-scanner.py" \
    "${FIXTURES}/bash-safe-command.json" 0

# Note: positive secret detection requires staged files with actual secrets
# in a real git repo. The scanner correctly skips when there are no staged files.
run_test "allows commit when no staged files have secrets" \
    "${HOOKS}/secret-scanner.py" \
    "${FIXTURES}/commit-with-secret.json" 0

echo ""
echo "=== Smart Formatter ==="

run_test "handles nonexistent file gracefully" \
    "${HOOKS}/smart-formatter.sh" \
    "${FIXTURES}/edit-nonexistent-file.json" 0

echo ""
echo "=== Change Tracker ==="

run_test "logs file modification for Write tool" \
    "${HOOKS}/change-tracker.sh" \
    "${FIXTURES}/write-tool-input.json" 0

run_test "handles nonexistent file gracefully" \
    "${HOOKS}/change-tracker.sh" \
    "${FIXTURES}/edit-nonexistent-file.json" 0

echo ""
echo "=== TDD Gate ==="

run_test "allows editing test files" \
    "${HOOKS}/tdd-gate.sh" \
    "${FIXTURES}/edit-test-file.json" 0

run_test "allows editing config files" \
    "${HOOKS}/tdd-gate.sh" \
    "${FIXTURES}/edit-config-file.json" 0

run_test "ignores non-Edit tool calls" \
    "${HOOKS}/tdd-gate.sh" \
    "${FIXTURES}/bash-safe-command.json" 0

echo ""
echo "=== Large File Blocker ==="

run_test "allows safe commands" \
    "${HOOKS}/large-file-blocker.sh" \
    "${FIXTURES}/bash-safe-command.json" 0

run_test "allows non-commit commands" \
    "${HOOKS}/large-file-blocker.sh" \
    "${FIXTURES}/commit-not-a-commit.json" 0

# Note: positive large file detection requires staged files exceeding 5MB
# in a real git repo. The blocker correctly passes when there are no large staged files.
run_test "allows commit when no staged files are large" \
    "${HOOKS}/large-file-blocker.sh" \
    "${FIXTURES}/commit-valid.json" 0

echo ""
echo "=== Env File Guard ==="

run_test "blocks writing to .env" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-env-file.json" 2

run_test "allows writing to .env.example" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-env-example.json" 0

run_test "blocks editing private key files" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/edit-private-key.json" 2

run_test "blocks writing to secrets directory" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-secrets-dir.json" 2

run_test "allows safe file writes" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-tool-input.json" 0

run_test "ignores non-Write/Edit tools" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/bash-safe-command.json" 0

echo ""
echo "=== GH Token Guard ==="

run_test "allows gh with GH_TOKEN set" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-gh-with-token.json" 0

run_test "blocks gh without GH_TOKEN" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-gh-without-token.json" 2

run_test "blocks gh auth switch" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-gh-auth-switch.json" 2

run_test "allows gh auth token (exempt)" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-gh-auth-token.json" 0

run_test "allows non-gh commands" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-safe-command.json" 0

echo ""
echo "=== GLab Token Guard ==="

run_test "allows glab with GITLAB_TOKEN set" \
    "${HOOKS}/glab-token-guard.py" \
    "${FIXTURES}/bash-glab-with-token.json" 0

run_test "blocks glab without GITLAB_TOKEN" \
    "${HOOKS}/glab-token-guard.py" \
    "${FIXTURES}/bash-glab-without-token.json" 2

run_test "blocks glab auth login" \
    "${HOOKS}/glab-token-guard.py" \
    "${FIXTURES}/bash-glab-auth-login.json" 2

run_test "allows non-glab commands" \
    "${HOOKS}/glab-token-guard.py" \
    "${FIXTURES}/bash-safe-command.json" 0

echo ""
echo "=== Scope Guard ==="

# scope-guard runs as a Stop hook and reads git state, not stdin tool input.
# It always exits 0 (non-blocking), so we verify it doesn't crash.
run_test "exits cleanly outside a git repo" \
    "${HOOKS}/scope-guard.sh" \
    "${FIXTURES}/bash-safe-command.json" 0

echo ""
echo "=== Results ==="
echo "  Passed: ${PASS}"
echo "  Failed: ${FAIL}"
echo ""

if [[ "${FAIL}" -gt 0 ]]; then
    exit 1
fi

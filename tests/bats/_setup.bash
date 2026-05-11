#!/usr/bin/env bash
# Shared bats-core setup for shell hook test suites.
#
# Spec: specs/2026-05-09-claude-config-state-of-art/plan.md 1.2.5.
#
# Source from each `tests/bats/<hook>.bats` file:
#
#   load _setup
#
# Then use the helpers below in setup() / @test blocks.

# Bail on undefined variables and pipe failures inside helpers.
set -u
set -o pipefail

# REPO_ROOT resolves to the repo containing this file. bats sets BATS_TEST_DIRNAME
# to the directory of the executing .bats file; the path back is two parents.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOKS_DIR="$REPO_ROOT/hooks"

export REPO_ROOT HOOKS_DIR

# Always mute audit logging in tests so the suite does not pollute the real
# audit log.
export CLAUDE_HOOK_AUDIT_DISABLE=1

# run_hook <hook-basename> <json-payload> [extra env=value ...]
#
# Resolves <hook-basename> against $HOOKS_DIR (with or without .py/.sh
# extension), runs it as a subprocess with the given JSON payload on stdin,
# and exposes the standard bats `$status`, `$output`, `$lines` after the call.
# Any positional arguments after the JSON are treated as KEY=VALUE env
# overrides applied for this invocation only.
#
# Usage:
#
#   @test "hook blocks dangerous command" {
#     run run_hook dangerous-command-blocker '{"tool_input":{"command":"rm -rf /"}}'
#     assert_blocked
#   }
run_hook() {
  local hook="$1"; shift
  local payload="$1"; shift
  local hook_path

  hook_path="$(resolve_hook "$hook")" || {
    echo "run_hook: hook not found: $hook" >&2
    return 127
  }

  if [ "$#" -gt 0 ]; then
    env "$@" CLAUDE_HOOK_AUDIT_DISABLE=1 \
      bash -c 'exec "$1" <<<"$2"' _ "$hook_path" "$payload"
  else
    bash -c 'exec "$1" <<<"$2"' _ "$hook_path" "$payload"
  fi
}

# resolve_hook <basename>: locates a hook by basename. Tries .py then .sh,
# then the bare name. Echoes the absolute path on success.
resolve_hook() {
  local name="$1"
  local candidate

  for ext in "" ".py" ".sh"; do
    candidate="$HOOKS_DIR/${name}${ext}"
    if [ -x "$candidate" ] || [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# assert_blocked: asserts the hook exited with code 2 (Claude Code's "block"
# exit code).  Call after `run run_hook ...`.
assert_blocked() {
  if [ "$status" -ne 2 ]; then
    echo "expected hook to block (exit 2) but got exit $status"
    echo "stdout: $output"
    return 1
  fi
}

# assert_allowed: asserts the hook exited with code 0.
assert_allowed() {
  if [ "$status" -ne 0 ]; then
    echo "expected hook to allow (exit 0) but got exit $status"
    echo "stdout: $output"
    return 1
  fi
}

# assert_stderr_contains <substring>: bats `run` merges stdout and stderr by
# default, so this matches against the merged output.
assert_stderr_contains() {
  local needle="$1"
  if [[ "$output" != *"$needle"* ]]; then
    echo "expected output to contain '$needle' but it did not"
    echo "actual: $output"
    return 1
  fi
}

# make_payload <tool> <key> <value> [<key> <value> ...]
#
# Builds a minimal JSON payload using `python3 -c`. Useful when the test
# wants to embed strings with quotes or newlines safely.
#
# Example:
#   payload="$(make_payload Bash command "rm -rf /")"
make_payload() {
  local tool="$1"; shift
  python3 -c "
import json, sys
tool, args = sys.argv[1], sys.argv[2:]
input_dict = dict(zip(args[::2], args[1::2]))
print(json.dumps({'tool_name': tool, 'tool_input': input_dict}))
" "$tool" "$@"
}

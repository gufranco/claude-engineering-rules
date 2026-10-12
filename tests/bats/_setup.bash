#!/usr/bin/env bash
# shellcheck disable=SC2016,SC2154
set -u
set -o pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOKS_DIR="$REPO_ROOT/hooks"
export REPO_ROOT HOOKS_DIR
export CLAUDE_HOOK_AUDIT_DISABLE=1
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
assert_blocked() {
  if [ "$status" -ne 2 ]; then
    echo "expected hook to block (exit 2) but got exit $status"
    echo "stdout: $output"
    return 1
  fi
}
assert_allowed() {
  if [ "$status" -ne 0 ]; then
    echo "expected hook to allow (exit 0) but got exit $status"
    echo "stdout: $output"
    return 1
  fi
}
assert_stderr_contains() {
  local needle="$1"
  if [[ "$output" != *"$needle"* ]]; then
    echo "expected output to contain '$needle' but it did not"
    echo "actual: $output"
    return 1
  fi
}
make_payload() {
  local tool="$1"; shift
  python3 -c "
import json, sys
tool, args = sys.argv[1], sys.argv[2:]
input_dict = dict(zip(args[::2], args[1::2]))
print(json.dumps({'tool_name': tool, 'tool_input': input_dict}))
" "$tool" "$@"
}

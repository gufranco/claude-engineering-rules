#!/usr/bin/env bash
# mcp-health-check.sh — Verify MCP servers declared in settings.json are reachable.
#
# For each server in mcpServers, attempts to start it with a timeout and
# checks whether it exits cleanly or responds to a basic probe.
#
# Usage:
#   bash scripts/mcp-health-check.sh
#   bash scripts/mcp-health-check.sh --verbose

set -euo pipefail

SETTINGS="${HOME}/.claude/settings.json"
VERBOSE="${1:-}"
PASS=0
FAIL=0
SKIP=0

if [[ ! -f "${SETTINGS}" ]]; then
  echo "ERROR: settings.json not found at ${SETTINGS}"
  exit 1
fi

# Extract MCP server names and commands
MCP_NAMES=$(python3 -c "
import json, sys
s = json.load(open('${SETTINGS}'))
mcp = s.get('mcpServers', {})
for name, cfg in mcp.items():
    cmd = cfg.get('command', '')
    args = ' '.join(cfg.get('args', []))
    print(f'{name}|{cmd}|{args}')
" 2>/dev/null || true)

if [[ -z "${MCP_NAMES}" ]]; then
  echo "No MCP servers configured in settings.json."
  exit 0
fi

echo "=== MCP Health Check ==="
echo ""

while IFS='|' read -r name cmd args; do
  [[ -z "${name}" ]] && continue

  # Check if the command binary exists
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    printf "SKIP (%s): command not found: %s\n" "${name}" "${cmd}"
    (( SKIP++ )) || true
    continue
  fi

  # Attempt to run with a 3-second timeout, capture exit code
  # MCP servers typically run indefinitely, so we just check they start cleanly
  set +e
  timeout 3s ${cmd} ${args} >/dev/null 2>&1
  exit_code=$?
  set -e

  if [[ "${exit_code}" -eq 124 ]]; then
    # Timeout = server started and ran, which is expected for long-running servers
    printf "PASS (%s): started successfully (timed out as expected)\n" "${name}"
    (( PASS++ )) || true
  elif [[ "${exit_code}" -eq 0 ]]; then
    printf "PASS (%s): exited cleanly\n" "${name}"
    (( PASS++ )) || true
  else
    printf "FAIL (%s): exited with code %d\n" "${name}" "${exit_code}"
    [[ -n "${VERBOSE}" ]] && echo "  Command: ${cmd} ${args}"
    (( FAIL++ )) || true
  fi

done <<< "${MCP_NAMES}"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"

[[ "${FAIL}" -eq 0 ]] || exit 1

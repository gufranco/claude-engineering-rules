#!/usr/bin/env bash
set -euo pipefail

SETTINGS="${HOME}/.claude/settings.json"
VERBOSE="${1:-}"
PASS=0
FAIL=0
SKIP=0
FIELD=$'\x1f'

if [[ ! -f "${SETTINGS}" ]]; then
  echo "ERROR: settings.json not found at ${SETTINGS}"
  exit 1
fi

MCP_SERVERS=$(SETTINGS="${SETTINGS}" python3 -c '
import json, os
with open(os.environ["SETTINGS"], encoding="utf-8") as handle:
    servers = json.load(handle).get("mcpServers", {})
for name, cfg in servers.items():
    print("\x1f".join([name, cfg.get("command", ""), *map(str, cfg.get("args", []))]))
')

if [[ -z "${MCP_SERVERS}" ]]; then
  echo "No MCP servers configured in settings.json."
  exit 0
fi

echo "=== MCP Health Check ==="
echo ""

while IFS="${FIELD}" read -r -a fields; do
  name="${fields[0]:-}"
  cmd="${fields[1]:-}"
  argv=("${fields[@]:2}")
  [[ -z "${name}" ]] && continue

  if ! command -v "${cmd}" >/dev/null 2>&1; then
    printf "SKIP (%s): command not found: %s\n" "${name}" "${cmd}"
    (( SKIP++ )) || true
    continue
  fi

  set +e
  timeout 3s "${cmd}" "${argv[@]}" >/dev/null 2>&1
  exit_code=$?
  set -e

  if [[ "${exit_code}" -eq 124 ]]; then
    printf "PASS (%s): started successfully (timed out as expected)\n" "${name}"
    (( PASS++ )) || true
  elif [[ "${exit_code}" -eq 0 ]]; then
    printf "PASS (%s): exited cleanly\n" "${name}"
    (( PASS++ )) || true
  else
    printf "FAIL (%s): exited with code %d\n" "${name}" "${exit_code}"
    [[ -n "${VERBOSE}" ]] && echo "  Command: ${cmd} ${argv[*]}"
    (( FAIL++ )) || true
  fi
done <<< "${MCP_SERVERS}"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"

[[ "${FAIL}" -eq 0 ]] || exit 1

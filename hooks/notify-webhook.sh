#!/usr/bin/env bash
# notify-webhook.sh — Send a notification when Claude Code finishes a response.
#
# Stop hook. Posts to a Slack/Discord-compatible webhook.
# Requires CLAUDE_NOTIFY_WEBHOOK env var. Exits 0 silently if unset.

set -euo pipefail

[[ -z "${CLAUDE_NOTIFY_WEBHOOK:-}" ]] && exit 0

PAYLOAD='{"text":"Claude Code: Response complete","username":"Claude Code"}'

curl -s -o /dev/null -w '' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "${PAYLOAD}" \
  "${CLAUDE_NOTIFY_WEBHOOK}" 2>/dev/null || true

exit 0

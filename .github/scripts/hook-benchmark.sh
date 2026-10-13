#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
THRESHOLD_MS=500

if [[ "${1:-}" == "--threshold" ]]; then
  THRESHOLD_MS="${2:?--threshold needs a value in milliseconds}"
fi

exec python3 "${ROOT}/hooks/_lib/bench_hooks.py" \
  --hooks-dir "${ROOT}/hooks" \
  --settings "${ROOT}/settings.json" \
  --iterations 3 \
  --threshold-ms "${THRESHOLD_MS}"

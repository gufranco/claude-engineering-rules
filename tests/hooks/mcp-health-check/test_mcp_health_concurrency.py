from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from _helpers.cov_env import apply_coverage_env

ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = ROOT / "hooks" / "mcp-health-check.py"
CALLS = 20


def _failure(tmp_home: Path) -> int:
    payload = {
        "tool_name": "mcp__flaky__read",
        "hook_event_name": "PostToolUse",
        "tool_input": {},
        "tool_response": {"isError": True},
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=apply_coverage_env(
            {**os.environ, "HOME": str(tmp_home), "CLAUDE_HOOK_AUDIT_DISABLE": "1"}
        ),
        timeout=30,
        check=False,
    )
    return proc.returncode


def test_parallel_failure_reports_are_all_counted(tmp_path):
    # Arrange
    (tmp_path / ".claude" / "cache").mkdir(parents=True)

    # Act
    with ThreadPoolExecutor(max_workers=CALLS) as pool:
        codes = list(pool.map(lambda _: _failure(tmp_path), range(CALLS)))

    # Assert
    state = json.loads((tmp_path / ".claude" / "cache" / "mcp-health.json").read_text())
    assert (set(codes), state["flaky"]["failures"]) == ({0}, CALLS)

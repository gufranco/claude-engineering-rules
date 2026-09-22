"""The session must be told when vault maintenance has gone quiet.

A maintenance loop that stops running produces exactly the same silence as one
with nothing to do. The run record gives the loop a second, loud channel, which
is the only way a fail-open component can report its own failure.

Rule source: ``rules/agent-operating-limits.md`` "Fail Closed".
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


HOOK = Path.home() / ".claude" / "hooks" / "vault-context-loader.py"
RECORD = ".maintenance.json"


def build_vault(tmp_path: Path, *, ran_days_ago: int | None) -> Path:
    root = tmp_path / "vault"
    (root / "wiki").mkdir(parents=True)
    (root / "index.md").write_text("# Index\n\n- nothing yet\n", encoding="utf-8")
    if ran_days_ago is not None:
        when = datetime.now(timezone.utc) - timedelta(days=ran_days_ago)
        (root / RECORD).write_text(
            json.dumps(
                {"ran_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "exit": 0, "steps": {}}
            ),
            encoding="utf-8",
        )
    return root


def run(root: Path) -> str:
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"hook_event_name": "SessionStart"}),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "SECOND_BRAIN_VAULT": str(root)},
    )
    return proc.stdout


def test_overdue_maintenance_is_reported(tmp_path):
    root = build_vault(tmp_path, ran_days_ago=30)

    out = run(root)

    assert "maintenance" in out.lower()
    assert "overdue" in out.lower()


def test_recent_maintenance_is_not_reported(tmp_path):
    root = build_vault(tmp_path, ran_days_ago=1)

    out = run(root)

    assert "overdue" not in out.lower()


def test_never_run_is_reported(tmp_path):
    root = build_vault(tmp_path, ran_days_ago=None)

    out = run(root)

    assert "maintenance" in out.lower()


def test_index_is_still_injected(tmp_path):
    root = build_vault(tmp_path, ran_days_ago=1)

    out = run(root)

    assert "nothing yet" in out

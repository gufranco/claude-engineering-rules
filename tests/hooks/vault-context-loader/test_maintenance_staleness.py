from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _helpers.cov_env import apply_coverage_env


HOOK = Path(__file__).resolve().parents[3] / "hooks" / "vault-context-loader.py"
RECORD = ".maintenance.json"
TIMEOUT_S = 30


def build_vault(
    tmp_path: Path, *, ran_days_ago: int | None, exit_code: int = 0
) -> Path:
    root = tmp_path / "vault"
    (root / "wiki").mkdir(parents=True)
    (root / "index.md").write_text("# Index\n\n- nothing yet\n", encoding="utf-8")
    if ran_days_ago is not None:
        when = datetime.now(timezone.utc) - timedelta(days=ran_days_ago)
        (root / RECORD).write_text(
            json.dumps(
                {
                    "ran_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "exit": exit_code,
                    "steps": {"vault-freshness": exit_code},
                }
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
        env=apply_coverage_env(
            {
                "PATH": "/usr/bin:/bin",
                "HOME": str(root.parent),
                "SECOND_BRAIN_VAULT": str(root),
                "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            }
        ),
        timeout=TIMEOUT_S,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]


def test_overdue_maintenance_is_reported(tmp_path):
    # Arrange
    root = build_vault(tmp_path, ran_days_ago=30)

    # Act
    out = run(root)

    # Assert
    assert "Vault maintenance is overdue: last run 30 days ago" in out


def test_recent_maintenance_is_not_reported(tmp_path):
    # Arrange
    root = build_vault(tmp_path, ran_days_ago=1)

    # Act
    out = run(root)

    # Assert
    assert "overdue" not in out


def test_never_run_is_reported(tmp_path):
    # Arrange
    root = build_vault(tmp_path, ran_days_ago=None)

    # Act
    out = run(root)

    # Assert
    assert "Vault maintenance has no run record, so it is overdue." in out


def test_index_is_still_injected(tmp_path):
    # Arrange
    root = build_vault(tmp_path, ran_days_ago=1)

    # Act
    out = run(root)

    # Assert
    assert "- nothing yet" in out


def test_a_recent_run_that_failed_is_reported(tmp_path):
    # Arrange
    root = build_vault(tmp_path, ran_days_ago=1, exit_code=1)

    # Act
    out = run(root)

    # Assert
    assert "and failed: vault-freshness." in out


def test_a_recent_run_that_passed_stays_quiet(tmp_path):
    # Arrange
    root = build_vault(tmp_path, ran_days_ago=1, exit_code=0)

    # Act
    out = run(root)

    # Assert
    assert "Vault maintenance" not in out

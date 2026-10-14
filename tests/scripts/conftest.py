from __future__ import annotations

from pathlib import Path

import pytest

from _helpers.audit_log_support import (
    audit_log,
)


@pytest.fixture
def hooks_dir(tmp_path: Path) -> Path:
    target = tmp_path / "hooks"
    target.mkdir()
    return target


@pytest.fixture
def isolated_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    log_dir = tmp_path / "logs"
    log_path = log_dir / "hooks.log"
    backup_path = log_dir / "hooks.log.1"
    monkeypatch.setattr(audit_log, "LOG_DIR", str(log_dir))
    monkeypatch.setattr(audit_log, "LOG_PATH", str(log_path))
    monkeypatch.setattr(audit_log, "BACKUP_PATH", str(backup_path))
    monkeypatch.delenv("CLAUDE_HOOK_AUDIT_DISABLE", raising=False)
    return log_path

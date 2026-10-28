from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import audit_log  # noqa: E402

REDACTED = "[REDACTED]"
AWS_STYLE_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
EXCERPT_LIMIT = 240
DETECTOR_TAG_LIMIT = 80
DEFECT_PATTERN_TAG_LIMIT = 64


Record = dict[str, object]


def isolate_audit_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    log_path = tmp_path / "logs" / "hooks.log"
    monkeypatch.setattr(audit_log, "LOG_DIR", str(log_path.parent))
    monkeypatch.setattr(audit_log, "LOG_PATH", str(log_path))
    monkeypatch.setattr(audit_log, "BACKUP_PATH", f"{log_path}.1")
    monkeypatch.delenv("CLAUDE_HOOK_AUDIT_DISABLE", raising=False)
    return log_path


def _read_records(log_path: Path) -> list[Record]:
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


__all__ = [
    "AWS_STYLE_KEY",
    "DEFECT_PATTERN_TAG_LIMIT",
    "DETECTOR_TAG_LIMIT",
    "EXCERPT_LIMIT",
    "REDACTED",
    "REPO_ROOT",
    "Record",
    "_read_records",
    "audit_log",
    "isolate_audit_log",
]

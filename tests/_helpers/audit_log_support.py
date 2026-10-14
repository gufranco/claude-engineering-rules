from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import audit_log  # noqa: E402

REDACTED = "[REDACTED]"
AWS_STYLE_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
EXCERPT_LIMIT = 240
DETECTOR_TAG_LIMIT = 80
DEFECT_PATTERN_TAG_LIMIT = 64


Record = dict[str, object]


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
]

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
from typing import Any, SupportsInt, cast

LOG_DIR = os.path.expanduser("~/.claude/logs")
LOG_PATH = os.path.join(LOG_DIR, "hooks.log")
BACKUP_PATH = LOG_PATH + ".1"
MAX_BYTES = 5 * 1024 * 1024
MAX_EXCERPT = 240
MAX_DETECTOR_TAG = 80
MAX_DEFECT_PATTERN_TAG = 64

ALLOWED_DECISION_CLASSES: frozenset[str] = frozenset(
    {"block", "allow", "modify", "defer", "ask", "bypass", "warn", "budget_exceeded"}
)

DEFECT_PATTERN_TAGS: frozenset[str] = frozenset(
    {
        "plausible-hallucination",
        "optimistic-error-handling",
        "shallow-validation",
        "copy-paste-drift",
        "missing-cleanup",
        "invented-api",
    }
)

_REDACT_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-ant-(?:admin-)?[a-zA-Z0-9_-]{20,}"),
    re.compile(r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"[rs]k_(?:live|test)_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[0-9a-zA-Z-]{10,}"),
    re.compile(r"hf_[A-Za-z0-9]{34,}"),
    re.compile(r"npm_[A-Za-z0-9]{36}"),
    re.compile(r"pypi-[A-Za-z0-9_-]{16,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+"),
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?:postgres|mysql|mongodb|redis)://[^\s'\"]+:[^\s'\"]+@"),
    re.compile(
        r"(?i)(password|passwd|pwd|secret|token|api_key|apikey)\s*[=:]\s*['\"][^'\"]{6,}['\"]"
    ),
]


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in _REDACT_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def _rotate_if_needed() -> None:
    try:
        size = os.path.getsize(LOG_PATH)
    except OSError:
        return
    if size < MAX_BYTES:
        return
    try:
        if os.path.exists(BACKUP_PATH):
            os.remove(BACKUP_PATH)
        os.rename(LOG_PATH, BACKUP_PATH)
    except OSError:
        return


_DROP: object = object()

_TAG_LIMITS: tuple[tuple[str, int], ...] = (
    ("detector_tag", MAX_DETECTOR_TAG),
    ("defect_pattern_tag", MAX_DEFECT_PATTERN_TAG),
)


def _decision_updates(fields: dict[str, object]) -> dict[str, object]:
    if "decision_class" not in fields:
        return {}
    dc = fields["decision_class"]
    if isinstance(dc, str) and dc in ALLOWED_DECISION_CLASSES:
        return {}
    return {"original_decision_class": dc, "decision_class": "warn"}


def _confidence_updates(fields: dict[str, object]) -> dict[str, object]:
    if "confidence_score" not in fields:
        return {}
    try:
        value = int(cast("SupportsInt | str", fields["confidence_score"]))
    except (TypeError, ValueError):
        return {"confidence_score": _DROP}
    return {"confidence_score": max(1, min(10, value))}


def _truncated_tag(value: object, limit: int) -> object:
    return value[:limit] if isinstance(value, str) else _DROP


def _tag_updates(fields: dict[str, object]) -> dict[str, object]:
    return {
        key: _truncated_tag(fields[key], limit)
        for key, limit in _TAG_LIMITS
        if key in fields
    }


def _normalize_schema(fields: dict[str, object]) -> dict[str, object]:
    updates = {
        **_decision_updates(fields),
        **_confidence_updates(fields),
        **_tag_updates(fields),
    }
    merged = {key: updates.get(key, value) for key, value in fields.items()}
    added = {key: value for key, value in updates.items() if key not in fields}
    return {
        key: value for key, value in {**merged, **added}.items() if value is not _DROP
    }


def record(**fields: Any) -> None:
    if os.environ.get("CLAUDE_HOOK_AUDIT_DISABLE") == "1":
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        _rotate_if_needed()
        fields = _normalize_schema(fields)
        if "command_excerpt" in fields and isinstance(fields["command_excerpt"], str):
            fields["command_excerpt"] = redact(fields["command_excerpt"])[:MAX_EXCERPT]
        fields.setdefault("cwd", os.getcwd())
        sid = (
            os.environ.get("CLAUDE_CODE_SESSION_ID")
            or os.environ.get("CLAUDE_SESSION_ID")
            or os.environ.get("SESSION_ID")
        )
        if sid and "session_id" not in fields:
            fields["session_id"] = sid
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **fields}
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                fh.write(line + "\n")
            finally:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except OSError as unlock_error:
                    sys.stderr.write(f"audit log: unlock failed: {unlock_error}\n")
    except Exception as error:
        sys.stderr.write(f"audit log: write failed: {error}\n")


def _add_text_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--level", default=None)
    parser.add_argument("--tool", default=None)
    parser.add_argument("--reason", default=None)
    parser.add_argument("--command", dest="command_excerpt", default=None)
    parser.add_argument("--bypass-env", dest="bypass_env", default=None)
    parser.add_argument("--session-id", dest="session_id", default=None)


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Append a record to ~/.claude/logs/hooks.log"
    )
    parser.add_argument("--hook", required=True)
    parser.add_argument(
        "--decision", required=True, choices=["block", "bypass", "warn", "allow"]
    )
    _add_text_flags(parser)
    parser.add_argument(
        "--decision-class",
        dest="decision_class",
        default=None,
        choices=sorted(ALLOWED_DECISION_CLASSES),
    )
    parser.add_argument("--detector-tag", dest="detector_tag", default=None)
    parser.add_argument("--defect-pattern-tag", dest="defect_pattern_tag", default=None)
    parser.add_argument(
        "--confidence-score",
        dest="confidence_score",
        type=int,
        default=None,
    )
    parser.add_argument("--file-path", dest="file_path", default=None)
    parser.add_argument("--latency-ms", dest="latency_ms", type=int, default=None)
    return parser


def _cli(argv: list[str]) -> int:
    args = _build_cli_parser().parse_args(argv)
    payload = {k: v for k, v in vars(args).items() if v is not None}
    record(**payload)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))

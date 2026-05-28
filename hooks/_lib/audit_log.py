"""Structured audit log shared by hooks.

Writes JSON Lines to ~/.claude/logs/hooks.log. Rotates the file when it grows
past 5 MiB by renaming to hooks.log.1, dropping the previous .1 if any. Keeps
one backup so the on-disk footprint stays bounded.

Usage from a Python hook:

    sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
    from _lib.audit_log import record, redact
    record(hook="dangerous-command-blocker", decision="block",
           reason="rm -rf /", tool="Bash",
           command_excerpt=redact(cmd)[:200])

Usage from a shell hook:

    python3 ~/.claude/hooks/_lib/audit_log.py \
        --hook large-file-blocker --decision block --tool Bash \
        --reason "file > 5MB" --command "$cmd"

The function never raises. Logging is best-effort.

Schema (spec 1.3.1):

    hook                basename of the hook module emitting the record
    decision            legacy decision label (block, allow, ...)
    decision_class      normalized decision label, validated against
                        `ALLOWED_DECISION_CLASSES`. When the caller passes an
                        unknown class, the value is preserved under
                        `original_decision_class` and the class is downgraded
                        to "warn" so summarizers never see invalid values.
    detector            legacy per-detector tag (free-form string)
    detector_tag        normalized per-detector tag, truncated to
                        `MAX_DETECTOR_TAG` characters
    defect_pattern_tag  AI-defect taxonomy tag from rules/ai-guardrails.md,
                        truncated to `MAX_DEFECT_PATTERN_TAG` characters
    confidence_score    1-10 inclusive integer, clamped on write
    reason              short human-readable reason
    file_path           target file path when relevant
    latency_ms          measured hook latency in milliseconds
    suppressed          True when a suppression marker silenced a finding
    command_excerpt     redacted, truncated command tail
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
from typing import Any

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

# High-precision token patterns. Subset of secret-scanner.py focused on
# values that commonly appear in command lines or tool payloads.
_REDACT_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-ant-(?:admin-)?[a-zA-Z0-9_-]{20,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
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
    """Return text with high-confidence secrets replaced by [REDACTED]."""
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


def _normalize_schema(fields: dict[str, Any]) -> dict[str, Any]:
    """Apply the structured-schema constraints from spec 1.3.1.

    Caller-provided values that violate the schema are repaired in place
    rather than dropped, so summarizers never see invalid records but
    hooks still see their data round-trip when they read the log later.
    """
    out = dict(fields)

    if "decision_class" in out:
        dc = out["decision_class"]
        if isinstance(dc, str) and dc in ALLOWED_DECISION_CLASSES:
            pass
        else:
            out["original_decision_class"] = dc
            out["decision_class"] = "warn"

    if "confidence_score" in out:
        try:
            value = int(out["confidence_score"])
            out["confidence_score"] = max(1, min(10, value))
        except (TypeError, ValueError):
            del out["confidence_score"]

    if "detector_tag" in out:
        dt = out["detector_tag"]
        if isinstance(dt, str):
            out["detector_tag"] = dt[:MAX_DETECTOR_TAG]
        else:
            del out["detector_tag"]

    if "defect_pattern_tag" in out:
        dpt = out["defect_pattern_tag"]
        if isinstance(dpt, str):
            out["defect_pattern_tag"] = dpt[:MAX_DEFECT_PATTERN_TAG]
        else:
            del out["defect_pattern_tag"]

    return out


def record(**fields: Any) -> None:
    """Append a JSON line to the audit log. Never raises."""
    if os.environ.get("CLAUDE_HOOK_AUDIT_DISABLE") == "1":
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        _rotate_if_needed()
        fields = _normalize_schema(fields)
        # Truncate command excerpts to keep lines bounded.
        if "command_excerpt" in fields and isinstance(fields["command_excerpt"], str):
            fields["command_excerpt"] = redact(fields["command_excerpt"])[:MAX_EXCERPT]
        # Auto-fill cwd and session id from environment when caller did not pass them.
        fields.setdefault("cwd", os.getcwd())
        sid = os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("SESSION_ID")
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
                except OSError:
                    pass
    except Exception:
        return


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Append a record to ~/.claude/logs/hooks.log"
    )
    parser.add_argument("--hook", required=True)
    parser.add_argument(
        "--decision", required=True, choices=["block", "bypass", "warn", "allow"]
    )
    parser.add_argument("--level", default=None)
    parser.add_argument("--tool", default=None)
    parser.add_argument("--reason", default=None)
    parser.add_argument("--command", dest="command_excerpt", default=None)
    parser.add_argument("--bypass-env", dest="bypass_env", default=None)
    parser.add_argument("--session-id", dest="session_id", default=None)
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
    args = parser.parse_args(argv)
    payload = {k: v for k, v in vars(args).items() if v is not None}
    record(**payload)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))

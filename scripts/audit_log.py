"""Structured audit log shared by hooks.

Writes JSON Lines to ~/.claude/logs/hooks.log. Rotates the file when it grows
past 5 MiB by renaming to hooks.log.1, dropping the previous .1 if any. Keeps
one backup so the on-disk footprint stays bounded.

Usage from a Python hook:

    sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
    from audit_log import record, redact
    record(hook="dangerous-command-blocker", decision="block",
           reason="rm -rf /", tool="Bash",
           command_excerpt=redact(cmd)[:200])

Usage from a shell hook:

    python3 ~/.claude/scripts/audit_log.py \
        --hook large-file-blocker --decision block --tool Bash \
        --reason "file > 5MB" --command "$cmd"

The function never raises. Logging is best-effort.
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
    re.compile(r"(?i)(password|passwd|pwd|secret|token|api_key|apikey)\s*[=:]\s*['\"][^'\"]{6,}['\"]"),
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


def record(**fields: Any) -> None:
    """Append a JSON line to the audit log. Never raises."""
    if os.environ.get("CLAUDE_HOOK_AUDIT_DISABLE") == "1":
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        _rotate_if_needed()
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
    parser = argparse.ArgumentParser(description="Append a record to ~/.claude/logs/hooks.log")
    parser.add_argument("--hook", required=True)
    parser.add_argument("--decision", required=True, choices=["block", "bypass", "warn", "allow"])
    parser.add_argument("--level", default=None)
    parser.add_argument("--tool", default=None)
    parser.add_argument("--reason", default=None)
    parser.add_argument("--command", dest="command_excerpt", default=None)
    parser.add_argument("--bypass-env", dest="bypass_env", default=None)
    parser.add_argument("--session-id", dest="session_id", default=None)
    args = parser.parse_args(argv)
    payload = {k: v for k, v in vars(args).items() if v is not None}
    record(**payload)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))

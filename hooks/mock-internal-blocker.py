#!/usr/bin/env python3
"""
mock-internal-blocker.py

PreToolUse hook that blocks mocks of internal infrastructure in tests.
Rule source: ~/.claude/rules/testing.md "Mocks Policy (STRICT)".

Bans jest.mock / vi.mock / unittest.mock.patch targeting:
  - Own services (anything under services/, repositories/, controllers/, domain/)
  - Database clients (db, prisma, @repo/prisma-client, mongoose, knex)
  - Cache and queue (redis, valkey, ioredis, bull, bullmq, sqs, kafka)
  - Internal packages (@repo/*, @org/*, ../services, ./services)

Only fires on test files. External APIs you do not own are still allowed
(e.g., 'axios', 'stripe', 'sendgrid'), per the rule.

Bypass:
  MOCK_INTERNAL_DISABLE=1
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


JS_TEST = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
)
PY_TEST_DIR = ("/tests/", "/test/", "_test.py", "/__tests__/")
PY_TEST_NAME = re.compile(r"(?:^|/)(?:test_[^/]*|conftest)\.py$")

INTERNAL_TARGETS = re.compile(
    r"""(?ix)
    ^(?:
      \.{1,2}/[^'"]*(?:services|repositor(?:y|ies)|controllers?|domain)
      |@repo/[^'"]*
      |@org/[^'"]*
      |@/[^'"]*(?:services|db)
      |~/[^'"]*services
      |\.{1,2}/db
      |(?:prisma|@prisma/client|mongoose|knex|ioredis|redis(?:/[a-z\-]+)?
        |valkey|bull(?:mq)?|@aws-sdk/client-sqs|kafkajs)$
    )
    """
)
PY_INTERNAL_TARGETS = re.compile(
    r"(?:^|\.)(?:services?|repositor(?:y|ies)|controllers?|domain|db|database)(?:\.|$)"
    r"|^(?:redis|sqlalchemy|psycopg2?|pymongo|celery|kombu|aioredis)(?:\.|$)",
    re.IGNORECASE,
)

PY_TARGETS = (PY_INTERNAL_TARGETS, INTERNAL_TARGETS)

JS_MOCK_CALL = re.compile(
    r"""(?:jest|vi|vitest|test\.mock|sinon|td|testdouble)\s*\.\s*mock\s*\(\s*['"]([^'"]+)['"]"""
)
PY_MOCK_CALL = re.compile(
    r"""(?:patch|patch\.object|mock\.patch|unittest\.mock\.patch)\s*\(\s*['"]([^'"]+)['"]"""
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def is_test_file(path: str) -> bool:
    if not path:
        return False
    p = path.lower()
    if any(p.endswith(s) for s in JS_TEST):
        return True
    if any(seg in p for seg in PY_TEST_DIR):
        return True
    return PY_TEST_NAME.search(p) is not None


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((fp, "content", c))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((fp, "new_string", c))
    elif tool == "MultiEdit":
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((fp, f"edits[{i}].new_string", c))
    return out


def find(text: str) -> list[str]:
    checks = ((JS_MOCK_CALL, (INTERNAL_TARGETS,)), (PY_MOCK_CALL, PY_TARGETS))
    return [
        f"{m.group(0)} -> '{m.group(1)}'"
        for call, patterns in checks
        for m in call.finditer(text)
        if any(pattern.search(m.group(1)) for pattern in patterns)
    ]


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("mock-internal-blocker"):
        _sys.exit(0)
    if os.environ.get("MOCK_INTERNAL_DISABLE") == "1":
        _audit(
            hook="mock-internal-blocker",
            decision="bypass",
            bypass_env="MOCK_INTERNAL_DISABLE",
        )
        return 0
    if is_bypassed("mock-internal-blocker"):
        return 0

    payload = read_hook_payload("mock-internal-blocker")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    findings: list[str] = []
    for path, field, text in items:
        if not is_test_file(path):
            continue
        hits = find(text)
        if hits:
            findings.append(f"  - {field} ({path}):")
            for h in hits:
                findings.append(f"      {h}")

    if not findings:
        return 0

    print(
        "Blocked: mocking internal infrastructure. "
        'Rule: ~/.claude/standards/testing.md "Mocks Policy (STRICT)".\n'
        + "\n".join(findings)
        + "\n\nFix: use a real database, real Redis, real services. Add them to "
        "docker-compose for the test environment. Mocks are only allowed for external APIs "
        "you do not own (Stripe, SendGrid, third-party HTTP), Time, and Randomness.\n"
        "Bypass (rare): set MOCK_INTERNAL_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(
        hook="mock-internal-blocker",
        decision="block",
        tool=tool,
        reason="internal infrastructure mock",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

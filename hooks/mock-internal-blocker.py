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

import json
import os
import re
import sys

JS_TEST = (".test.ts", ".test.tsx", ".test.js", ".test.jsx",
           ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx")
PY_TEST_DIR = ("/tests/", "/test/", "_test.py", "/__tests__/")

INTERNAL_TARGETS = re.compile(
    r"""(?ix)
    ^(?:                              # the import path / dotted name
      \./[^'"]*services
      |\.\./[^'"]*services
      |\./[^'"]*repositor(?:y|ies)
      |\.\./[^'"]*repositor(?:y|ies)
      |\./[^'"]*controllers?
      |\.\./[^'"]*controllers?
      |\./[^'"]*domain
      |\.\./[^'"]*domain
      |@repo/[^'"]*
      |@org/[^'"]*
      |@/[^'"]*services
      |@/[^'"]*db
      |~/[^'"]*services
      |\.\./db
      |\./db
      |prisma
      |@prisma/client
      |mongoose
      |knex
      |ioredis
      |redis(?:/[a-z\-]*)?
      |valkey
      |bull(?:mq)?
      |@aws-sdk/client-sqs
      |kafkajs
    )
    """
)

JS_MOCK_CALL = re.compile(
    r"""(?:jest|vi|vitest|test\.mock|sinon|td|testdouble)\s*\.\s*mock\s*\(\s*['"]([^'"]+)['"]"""
)
PY_MOCK_CALL = re.compile(
    r"""(?:patch|patch\.object|mock\.patch|unittest\.mock\.patch)\s*\(\s*['"]([^'"]+)['"]"""
)


def is_test_file(path: str) -> bool:
    if not path:
        return False
    p = path.lower()
    if any(p.endswith(s) for s in JS_TEST):
        return True
    if any(seg in p for seg in PY_TEST_DIR):
        return True
    return False


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
    hits: list[str] = []
    for pat in (JS_MOCK_CALL, PY_MOCK_CALL):
        for m in pat.finditer(text):
            target = m.group(1)
            if INTERNAL_TARGETS.match(target):
                hits.append(f"{m.group(0)} -> '{target}'")
    return hits


def main() -> int:
    if os.environ.get("MOCK_INTERNAL_DISABLE") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

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
        "Rule: ~/.claude/rules/testing.md \"Mocks Policy (STRICT)\".\n"
        + "\n".join(findings)
        + "\n\nFix: use a real database, real Redis, real services. Add them to "
        "docker-compose for the test environment. Mocks are only allowed for external APIs "
        "you do not own (Stripe, SendGrid, third-party HTTP), Time, and Randomness.\n"
        "Bypass (rare): set MOCK_INTERNAL_DISABLE=1.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

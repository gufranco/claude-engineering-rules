#!/usr/bin/env python3
"""Inject the vault catalog at session start.

A session that does not know what the vault already holds re-derives knowledge
it has and files duplicates of notes that exist. The index is the cheapest
possible answer to "what do we already know", so it goes in once, at the start,
rather than being searched for repeatedly.

Read-only. This hook never writes to the vault.

Bypass: set ``VAULT_CONTEXT_DISABLE=1`` in a parent shell.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from _lib import knowledge_notes as kn
except ImportError:  # pragma: no cover
    sys.exit(0)

import os  # noqa: E402

ENV_VAR = "VAULT_CONTEXT_DISABLE"
MAX_CHARS = 8000
PREAMBLE = (
    "The second brain vault is at {root}.\n"
    "It is the durable store for knowledge no repository owns. Its catalog follows.\n"
    "Read a note before answering from it, and never claim it holds something it does not.\n"
    "File new knowledge with /brain capture, which owns the note grammar.\n\n"
)


def main() -> int:
    if os.environ.get(ENV_VAR) == "1":
        return 0
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    root = kn.vault_root()
    if root is None:
        return 0
    index = root / "index.md"
    try:
        body = index.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n\n[index truncated at 8000 characters]"
    context = PREAMBLE.format(root=root) + body
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

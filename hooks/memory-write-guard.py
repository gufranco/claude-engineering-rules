#!/usr/bin/env python3
"""Keep the session memory directory a generated artifact, when a vault exists.

Where a second brain vault is configured, it is the single source of truth for
durable knowledge and the memory directory is compiled from it. The harness's
built-in instruction describes writing memory files directly, which bypasses
the vault and loses the two things the vault adds: a record of when a fact was
learned and where it came from, and a token budget that demotes rather than
growing without bound.

This hook blocks a direct Write or Edit into the memory directory unless the
payload carries ``generated_from``, which only ``/brain compile`` emits.
``MEMORY.md`` is exempt, being the index the compile maintains.

The vault is optional and personal. With ``SECOND_BRAIN_VAULT`` unset or
pointing nowhere, this hook exits silently: the harness default is then the
only way to record anything, and blocking it would strand the user.

Bypass: set ``MEMORY_WRITE_GUARD_DISABLE=1`` in a parent shell. The legitimate
case is migrating a pre-existing hand-written file into the vault.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

GENERATED_MARKER = "generated_from"
EXEMPT_BASENAMES = {"MEMORY.md"}
REQUIRED_PATH_PARTS = (".claude", "projects")
MEMORY_DIR_LEAF = "memory"
WATCHED_TOOLS = {"Write", "Edit", "MultiEdit"}


def _vault_configured() -> bool:
    raw = os.environ.get("SECOND_BRAIN_VAULT", "").strip()
    if not raw:
        return False
    try:
        return Path(raw).expanduser().is_dir()
    except OSError:
        return False


def _is_memory_path(path: str) -> bool:
    if not path:
        return False
    try:
        parts = Path(path).expanduser().parts
    except (OSError, ValueError):
        return False
    if MEMORY_DIR_LEAF not in parts:
        return False
    return all(part in parts for part in REQUIRED_PATH_PARTS)


def _payload_text(tool_input: dict) -> str:
    for key in ("content", "new_string", "new_str"):
        value = tool_input.get(key)
        if isinstance(value, str):
            return value
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        return "\n".join(
            edit.get("new_string", "") for edit in edits if isinstance(edit, dict)
        )
    return ""


def main() -> int:
    if os.environ.get("MEMORY_WRITE_GUARD_DISABLE") == "1":
        return 0
    if not _vault_configured():
        return 0

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(event, dict):
        return 0

    if event.get("tool_name") not in WATCHED_TOOLS:
        return 0

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not _is_memory_path(file_path):
        return 0
    if Path(file_path).name in EXEMPT_BASENAMES:
        return 0
    if GENERATED_MARKER in _payload_text(tool_input):
        return 0

    sys.stderr.write(
        "BLOCKED: the memory directory is generated from the vault, not written "
        "by hand.\n\n"
        f"  {file_path}\n\n"
        "A hand written memory file records neither when the fact was learned "
        "nor where it came from, and it escapes the compile's token budget.\n\n"
        "Instead:\n"
        "  1. Capture the fact as a vault note carrying `memory: true` and a\n"
        "     `memory-scope` of user, feedback, project, or reference.\n"
        "  2. Run `/brain compile` to regenerate this directory.\n\n"
        'Rule: CLAUDE.md "Knowledge Single Source of Truth", '
        "rules/knowledge-notes.md\n"
        "Bypass when migrating a pre-existing file: "
        "export MEMORY_WRITE_GUARD_DISABLE=1\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

from pathlib import Path

HOOK = "knowledge-note-guard"


GOOD = """---
date: 2026-08-18
type: concept
tags: [concept]
ai-first: true
---

## For future agent

What this note holds and why it was saved.

Some timeless prose about the idea.
"""


def note(vault: Path, rel: str) -> str:
    return str(vault / rel)


LEGACY = GOOD.replace(
    "Some timeless prose about the idea.",
    "The backlog has 42 open tasks.\n\nSome timeless prose about the idea.",
)

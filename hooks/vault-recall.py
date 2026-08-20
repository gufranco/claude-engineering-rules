#!/usr/bin/env python3
"""Inject the vault notes most relevant to the prompt, on every turn.

The session-start loader puts the catalog in once. That answers "what exists"
but not "what is relevant now", so a note filed weeks ago stays unread while
the same problem is solved again from scratch.

This hook ranks the prompt against every note and injects the closest few. It
reuses the ranking function the vault's own retrieval evaluation scores, so
`/brain eval` measures this hook rather than something merely similar to it,
and a recall regression is a warning that automatic recall got worse.

Read-only. This hook never writes to the vault.

Silence is the default. A wrong injection costs context on every turn, so the
hook emits nothing unless the vault resolves, the prompt is substantial, and a
note clears the score floor.

Bypass: set ``VAULT_RECALL_DISABLE=1`` in a parent shell.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

ENV_VAR = "VAULT_RECALL_DISABLE"
VAULT_VAR = "SECOND_BRAIN_VAULT"
MIN_PROMPT_WORDS = 4
MAX_NOTES = 3
MAX_CHARS = 2000
PREAMBLE_HEADING = "## For future agent"

HEADER = (
    "Possibly relevant notes already in the second brain vault, ranked against "
    "this prompt. Read a note before answering from it. Their presence here is "
    "a lexical match, never a guarantee of relevance.\n\n"
)


def resolve_vault() -> Path | None:
    raw = os.environ.get(VAULT_VAR)
    if not raw:
        return None
    root = Path(raw)
    return root if root.is_dir() else None


def load_ranker(root: Path) -> ModuleType | None:
    target = root / ".ci" / "retrieval-eval.py"
    if not target.is_file():
        return None
    sys.path.insert(0, str(target.parent))
    spec = importlib.util.spec_from_file_location("_vault_ranker", target)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        return None
    return module


def read_prompt() -> str:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    prompt = payload.get("prompt")
    return prompt if isinstance(prompt, str) else ""


def preamble_of(root: Path, title: str) -> str:
    for path in root.rglob(f"{title}.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if PREAMBLE_HEADING not in text:
            return ""
        after = text.split(PREAMBLE_HEADING, 1)[1].lstrip("\n")
        return after.split("\n##", 1)[0].strip()
    return ""


def render(root: Path, titles: list[str]) -> str:
    blocks = []
    for title in titles:
        summary = preamble_of(root, title)
        if not summary:
            continue
        blocks.append(f"### {title}\n\n{summary}\n")
    if not blocks:
        return ""
    return (HEADER + "\n".join(blocks))[:MAX_CHARS]


def main() -> int:
    if os.environ.get(ENV_VAR) == "1":
        return 0
    prompt = read_prompt()
    if len(prompt.split()) < MIN_PROMPT_WORDS:
        return 0
    root = resolve_vault()
    if root is None:
        return 0
    ranker = load_ranker(root)
    if ranker is None:
        return 0
    try:
        index = ranker.build_index(root)
        titles = ranker.search(index, prompt, MAX_NOTES)
    except Exception:
        return 0
    if not titles:
        return 0
    output = render(root, titles)
    if output:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

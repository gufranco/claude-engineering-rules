#!/usr/bin/env python3
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
SCOPE_OVERSAMPLE = 6
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


def read_payload() -> tuple[str, str]:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return "", ""
    if not isinstance(payload, dict):
        return "", ""
    prompt = payload.get("prompt")
    cwd = payload.get("cwd")
    return (
        prompt if isinstance(prompt, str) else "",
        cwd if isinstance(cwd, str) else "",
    )


def load_notespec(root: Path) -> ModuleType | None:
    target = root / ".ci" / "notespec.py"
    if not target.is_file():
        return None
    spec = importlib.util.spec_from_file_location("_vault_notespec", target)
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


def note_text(root: Path, title: str) -> tuple[Path, str] | None:
    for path in root.rglob(f"{title}.md"):
        return path, path.read_text(encoding="utf-8", errors="replace")
    return None


def in_scope(kn: ModuleType | None, text: str, cwd: str) -> bool:
    if kn is None:
        return True
    fields = kn.parse_frontmatter(text) or {}
    patterns = kn.scope_patterns(fields)
    if not patterns:
        return True
    return kn.scope_allows(patterns, cwd or os.getcwd())


def preamble_of(text: str) -> str:
    if PREAMBLE_HEADING not in text:
        return ""
    after = text.split(PREAMBLE_HEADING, 1)[1].lstrip("\n")
    return after.split("\n##", 1)[0].strip()


def render(root: Path, titles: list[str], kn: ModuleType | None, cwd: str) -> str:
    blocks = []
    for title in titles:
        found = note_text(root, title)
        if found is None:
            continue
        _, text = found
        if not in_scope(kn, text, cwd):
            continue
        summary = preamble_of(text)
        if not summary:
            continue
        blocks.append(f"### {title}\n\n{summary}\n")
        if len(blocks) == MAX_NOTES:
            break
    if not blocks:
        return ""
    return (HEADER + "\n".join(blocks))[:MAX_CHARS]


def main() -> int:
    if os.environ.get(ENV_VAR) == "1":
        return 0
    prompt, cwd = read_payload()
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
        titles = ranker.search(index, prompt, MAX_NOTES * SCOPE_OVERSAMPLE)
    except Exception:
        return 0
    if not titles:
        return 0
    output = render(root, titles, load_notespec(root), cwd)
    if output:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

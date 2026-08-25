"""Tests for hooks/vault-recall.py.

The hook injects the vault notes most relevant to a prompt. It must stay
silent whenever it cannot be confident, because a wrong injection costs
context on every single turn.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "hooks" / "vault-recall.py"

_TESTS_DIR = REPO_ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402


RANKER_STUB = '''"""Stand-in for the ranker the vault supplies at `.ci/retrieval-eval.py`.

The hook loads whatever module sits at that path and calls `build_index` then
`search`. The real implementation lives in the vault, a separate store this
repository neither owns nor ships, so these tests exercise the hook against a
controlled two-function stub. That keeps the suite runnable on any machine, and
keeps it honest about what it covers: the hook's own silent-versus-inject
behaviour, never the vault's retrieval quality.
"""

from __future__ import annotations

from pathlib import Path

MIN_TOKEN = 4
MIN_OVERLAP = 2


def _tokens(text):
    folded = "".join(c.lower() if c.isalnum() else " " for c in text)
    return {word for word in folded.split() if len(word) >= MIN_TOKEN}


def build_index(root):
    index = {}
    for path in Path(root).rglob("*.md"):
        index[path.stem] = _tokens(path.read_text(encoding="utf-8", errors="replace"))
    return index


def search(index, prompt, limit):
    wanted = _tokens(prompt)
    scored = [
        (len(wanted & tokens), title)
        for title, tokens in index.items()
        if len(wanted & tokens) >= MIN_OVERLAP
    ]
    scored.sort(reverse=True)
    return [title for _, title in scored[:limit]]
'''


def build_vault(base: Path) -> Path:
    root = base / "vault"
    (root / "wiki" / "concepts").mkdir(parents=True)
    (root / ".ci").mkdir()
    (root / ".ci" / "retrieval-eval.py").write_text(RANKER_STUB)
    (root / "index.md").write_text(
        "---\ndate: 2026-08-20\ntype: index\ntags: [index]\nai-first: true\n---\n\n"
        "## For future agent\n\nCatalog.\n"
    )
    (
        root / "wiki" / "concepts" / "Postgres connection pooling exhaustion.md"
    ).write_text(
        "---\ndate: 2026-08-20\ntype: concept\ntags: [concept]\nai-first: true\n---\n\n"
        "## For future agent\n\nWhy a Postgres pool exhausts under load.\n"
    )
    return root


def run(hook_input: dict, vault: Path | None, env_extra: dict | None = None) -> str:
    import os

    env = dict(os.environ)
    env.pop("VAULT_RECALL_DISABLE", None)
    if vault is not None:
        env["SECOND_BRAIN_VAULT"] = str(vault)
    else:
        env.pop("SECOND_BRAIN_VAULT", None)
    env.update(env_extra or {})
    env = apply_coverage_env(env)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_injects_the_matching_note(tmp_path):
    vault = build_vault(tmp_path)

    out = run({"prompt": "our postgres pool keeps exhausting under load"}, vault)

    assert "Postgres connection pooling exhaustion" in out


def test_silent_when_nothing_matches(tmp_path):
    vault = build_vault(tmp_path)

    out = run({"prompt": "what is the weather in lisbon tomorrow"}, vault)

    assert out.strip() == ""


def test_silent_when_the_vault_is_absent(tmp_path):
    out = run({"prompt": "our postgres pool keeps exhausting under load"}, None)

    assert out.strip() == ""


def test_silent_when_disabled(tmp_path):
    vault = build_vault(tmp_path)

    out = run(
        {"prompt": "our postgres pool keeps exhausting under load"},
        vault,
        {"VAULT_RECALL_DISABLE": "1"},
    )

    assert out.strip() == ""


@pytest.mark.parametrize("prompt", ["", "yes", "do it", "run the tests"])
def test_silent_on_short_prompts(tmp_path, prompt):
    vault = build_vault(tmp_path)

    out = run({"prompt": prompt}, vault)

    assert out.strip() == ""


def test_survives_malformed_input(tmp_path):
    result = subprocess.run(
        [sys.executable, str(HOOK)], input="not json", capture_output=True, text=True
    )

    assert result.returncode == 0
    assert result.stdout.strip() == ""

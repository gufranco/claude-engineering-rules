from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from _helpers.cov_env import apply_coverage_env

HOOK = Path(__file__).resolve().parents[3] / "hooks" / "vault-recall.py"
PROMPT = "our postgres pool keeps exhausting under load"

RANKER_STUB = """from __future__ import annotations

from pathlib import Path


def build_index(root):
    return sorted(path.stem for path in Path(root).rglob("*.md") if path.stem != "index")


def search(index, prompt, limit):
    return index[:limit]
"""

NOTESPEC_STUB = """from __future__ import annotations


def parse_frontmatter(text):
    head = text.split("---", 2)[1]
    pairs = [line.split(":", 1) for line in head.splitlines() if ":" in line]
    return {key.strip(): value.strip() for key, value in pairs}


def scope_patterns(fields):
    raw = fields.get("scope-paths", "").strip("[]")
    return [part.strip() for part in raw.split(",") if part.strip()]


def scope_allows(patterns, cwd):
    return any(str(cwd).startswith(pattern) for pattern in patterns)
"""


def _note(root: Path, title: str, scope: str, summary: str) -> None:
    scope_line = f"scope-paths: [{scope}]\n" if scope else ""
    (root / "wiki" / "concepts" / f"{title}.md").write_text(
        "---\ndate: 2026-10-13\ntype: concept\ntags: [concept]\nai-first: true\n"
        f"{scope_line}---\n\n## For future agent\n\n{summary}\n",
        encoding="utf-8",
    )


def _vault(base: Path, project: Path, other: Path) -> Path:
    root = base / "vault"
    (root / "wiki" / "concepts").mkdir(parents=True)
    (root / ".ci").mkdir()
    (root / ".ci" / "retrieval-eval.py").write_text(RANKER_STUB, encoding="utf-8")
    (root / ".ci" / "notespec.py").write_text(NOTESPEC_STUB, encoding="utf-8")
    _note(root, "A pool note for the other project", str(other), "Other project only.")
    _note(root, "B pool note for this project", str(project), "This project only.")
    _note(root, "C pool note for everyone", "", "Holds everywhere.")
    return root


def _run(vault: Path, cwd: Path) -> str:
    inherited = {k: v for k, v in os.environ.items() if k != "VAULT_RECALL_DISABLE"}
    env = apply_coverage_env({**inherited, "SECOND_BRAIN_VAULT": str(vault)})
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"prompt": PROMPT, "cwd": str(cwd)}),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    return proc.stdout


def test_a_note_scoped_to_another_project_is_not_injected(tmp_path: Path) -> None:
    # Arrange
    project = tmp_path / "work" / "alpha"
    vault = _vault(tmp_path, project, tmp_path / "work" / "beta")

    # Act
    out = _run(vault, project)

    # Assert
    assert ("Other project only." in out, "This project only." in out) == (False, True)


def test_a_global_note_is_injected_in_every_project(tmp_path: Path) -> None:
    # Arrange
    project = tmp_path / "work" / "gamma"
    vault = _vault(tmp_path, tmp_path / "work" / "alpha", tmp_path / "work" / "beta")

    # Act
    out = _run(vault, project)

    # Assert
    assert ("Holds everywhere." in out, "project only." in out) == (True, False)


def test_scope_is_ignored_when_the_vault_has_no_notespec(tmp_path: Path) -> None:
    # Arrange
    project = tmp_path / "work" / "alpha"
    vault = _vault(tmp_path, project, tmp_path / "work" / "beta")
    (vault / ".ci" / "notespec.py").unlink()

    # Act
    out = _run(vault, project)

    # Assert
    assert "Other project only." in out

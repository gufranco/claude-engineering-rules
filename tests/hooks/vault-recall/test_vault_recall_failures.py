from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.cov_env import apply_coverage_env

HOOK = Path(__file__).resolve().parents[3] / "hooks" / "vault-recall.py"
PROMPT = "our postgres pool keeps exhausting under load"
LISTING_RANKER = """from __future__ import annotations


def build_index(root):
    return None


def search(index, prompt, limit):
    return {titles!r}
"""


def _vault(base: Path, ranker: str | None, notes: dict[str, str]) -> Path:
    root = base / "vault"
    (root / "wiki").mkdir(parents=True)
    (root / ".ci").mkdir()
    if ranker is not None:
        (root / ".ci" / "retrieval-eval.py").write_text(ranker, encoding="utf-8")
    for title, body in notes.items():
        (root / "wiki" / f"{title}.md").write_text(body, encoding="utf-8")
    return root


def _note(summary: str) -> str:
    return f"---\ntype: concept\n---\n\n## For future agent\n\n{summary}\n"


def _run(vault: Path, stdin: str) -> subprocess.CompletedProcess[str]:
    inherited = {k: v for k, v in os.environ.items() if k != "VAULT_RECALL_DISABLE"}
    env = apply_coverage_env({**inherited, "SECOND_BRAIN_VAULT": str(vault)})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )


def _prompt() -> str:
    return json.dumps({"prompt": PROMPT})


@pytest.mark.parametrize(
    "ranker",
    [
        None,
        "raise RuntimeError('broken ranker')\n",
        "def build_index(root):\n    raise OSError('io')\n",
    ],
    ids=["missing", "fails-on-import", "fails-on-index"],
)
def test_a_missing_or_failing_ranker_injects_nothing(
    tmp_path: Path, ranker: str | None
) -> None:
    # Arrange
    vault = _vault(tmp_path, ranker, {"Pool": _note("Pool summary.")})

    # Act
    proc = _run(vault, _prompt())

    # Assert
    assert (proc.returncode, proc.stdout) == (0, "")


@pytest.mark.parametrize("stdin", ["[1, 2]", "not json"], ids=["list", "malformed"])
def test_a_payload_that_is_not_an_object_injects_nothing(
    tmp_path: Path, stdin: str
) -> None:
    # Arrange
    vault = _vault(
        tmp_path, LISTING_RANKER.format(titles=["Pool"]), {"Pool": _note("x")}
    )

    # Act
    proc = _run(vault, stdin)

    # Assert
    assert (proc.returncode, proc.stdout) == (0, "")


def test_titles_without_a_file_or_a_preamble_are_skipped(tmp_path: Path) -> None:
    # Arrange
    ranker = LISTING_RANKER.format(titles=["Missing", "Bare", "Pool"])
    notes = {
        "Bare": "---\ntype: concept\n---\n\nNo preamble.\n",
        "Pool": _note("Pool summary."),
    }
    vault = _vault(tmp_path, ranker, notes)

    # Act
    proc = _run(vault, _prompt())

    # Assert
    assert (
        "### Pool" in proc.stdout,
        "Bare" in proc.stdout,
        "Missing" in proc.stdout,
    ) == (
        True,
        False,
        False,
    )


def test_injection_stops_at_three_notes(tmp_path: Path) -> None:
    # Arrange
    titles = ["One", "Two", "Three", "Four"]
    vault = _vault(
        tmp_path,
        LISTING_RANKER.format(titles=titles),
        {title: _note(f"{title} summary.") for title in titles},
    )

    # Act
    proc = _run(vault, _prompt())

    # Assert
    assert [title for title in titles if f"### {title}" in proc.stdout] == [
        "One",
        "Two",
        "Three",
    ]


def test_a_notespec_that_fails_to_import_disables_scope_filtering(
    tmp_path: Path,
) -> None:
    # Arrange
    vault = _vault(
        tmp_path,
        LISTING_RANKER.format(titles=["Pool"]),
        {
            "Pool": "---\nscope-paths: [/nowhere]\n---\n\n## For future agent\n\nPool summary.\n"
        },
    )
    (vault / ".ci" / "notespec.py").write_text(
        "raise ImportError('x')\n", encoding="utf-8"
    )

    # Act
    proc = _run(vault, _prompt())

    # Assert
    assert "### Pool" in proc.stdout

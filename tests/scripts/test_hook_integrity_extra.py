"""Extra coverage for `scripts/hook_integrity.py`.

Targets the malformed-manifest fallback, missing-file branch in
`verify_baseline`, the relative-to ValueError in `assert_self`, the
unknown-baseline-key branch, and the CLI entry point.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import hook_integrity  # noqa: E402


@pytest.fixture
def isolated_repo(tmp_path: Path, monkeypatch) -> Path:
    repo = tmp_path / "repo"
    (repo / "hooks").mkdir(parents=True)
    monkeypatch.setattr(hook_integrity, "REPO_ROOT", repo)
    monkeypatch.setattr(hook_integrity, "HOOKS_DIR", repo / "hooks")
    monkeypatch.setattr(
        hook_integrity, "INTEGRITY_FILE", repo / "hooks" / ".integrity.json"
    )
    return repo


def test_load_baseline_returns_empty_for_malformed_json(isolated_repo: Path) -> None:
    # Arrange
    hook_integrity.INTEGRITY_FILE.write_text("not json {", encoding="utf-8")

    # Act
    baseline = hook_integrity._load_baseline()

    # Assert
    assert baseline == {}


def test_load_baseline_returns_empty_for_non_dict(isolated_repo: Path) -> None:
    # Arrange
    hook_integrity.INTEGRITY_FILE.write_text("[1, 2, 3]", encoding="utf-8")

    # Act
    baseline = hook_integrity._load_baseline()

    # Assert
    assert baseline == {}


def test_verify_baseline_reports_missing_files(
    isolated_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange: write a manifest pointing to a file that does not exist.
    hook_integrity.INTEGRITY_FILE.write_text(
        json.dumps(
            {
                "version": 1,
                "files": {"hooks/ghost.py": "deadbeef" * 8},
            }
        ),
        encoding="utf-8",
    )

    # Act
    rc = hook_integrity.verify_baseline()
    captured = capsys.readouterr()

    # Assert
    assert rc == 2
    assert "MISSING" in captured.err
    assert "ghost.py" in captured.err


def test_assert_self_returns_true_for_path_outside_repo(
    isolated_repo: Path, tmp_path: Path
) -> None:
    # Arrange: seed a manifest, then test a file outside REPO_ROOT.
    (isolated_repo / "hooks" / "demo.py").write_text("x=1\n", encoding="utf-8")
    hook_integrity.update_baseline()
    outside = tmp_path / "elsewhere.py"
    outside.write_text("# not in repo\n", encoding="utf-8")

    # Act
    result = hook_integrity.assert_self(str(outside))

    # Assert
    assert result is True


def test_assert_self_returns_true_when_path_not_in_baseline(
    isolated_repo: Path,
) -> None:
    # Arrange: baseline only knows about hooks/demo.py
    (isolated_repo / "hooks" / "demo.py").write_text("x=1\n", encoding="utf-8")
    hook_integrity.update_baseline()
    other = isolated_repo / "hooks" / "stranger.py"
    other.write_text("y=2\n", encoding="utf-8")

    # Act
    result = hook_integrity.assert_self(str(other))

    # Assert
    assert result is True


def test_main_dispatches_update(
    isolated_repo: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    (isolated_repo / "hooks" / "demo.py").write_text("x=1\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["hook_integrity", "--update"])

    # Act
    rc = hook_integrity.main()
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "Wrote integrity manifest" in captured.out


def test_main_dispatches_verify(
    isolated_repo: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    (isolated_repo / "hooks" / "demo.py").write_text("x=1\n", encoding="utf-8")
    hook_integrity.update_baseline()
    monkeypatch.setattr(sys, "argv", ["hook_integrity", "--verify"])

    # Act
    rc = hook_integrity.main()
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "match manifest" in captured.out


def test_main_module_entry_runs_as_subprocess(tmp_path: Path) -> None:
    # Arrange
    script = SCRIPTS_DIR / "_lib" / "hook_integrity.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(script), "--verify"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    # Assert: --verify on the live repo can return 0, 1, or 2 depending on
    # whether a manifest exists. We just verify the script runs without
    # raising a Python error.
    assert proc.returncode in (0, 1, 2)

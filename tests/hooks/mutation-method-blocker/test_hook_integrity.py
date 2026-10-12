from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

from _lib import hook_integrity  # noqa: E402


@pytest.fixture
def isolated_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    (repo / "hooks").mkdir(parents=True)
    monkeypatch.setattr(hook_integrity, "REPO_ROOT", repo)
    monkeypatch.setattr(hook_integrity, "HOOKS_DIR", repo / "hooks")
    monkeypatch.setattr(
        hook_integrity, "INTEGRITY_FILE", repo / "hooks" / ".integrity.json"
    )
    return repo


def _write_hook(repo: Path, name: str, content: str) -> Path:
    path = repo / "hooks" / name
    path.write_text(content, encoding="utf-8")
    return path


def test_update_writes_manifest_with_correct_sha256(isolated_repo: Path) -> None:
    # Arrange
    _write_hook(isolated_repo, "demo.py", "print('hello')\n")
    expected = hashlib.sha256(b"print('hello')\n").hexdigest()

    # Act
    code = hook_integrity.update_baseline()

    # Assert
    manifest = json.loads(
        (isolated_repo / "hooks" / ".integrity.json").read_text(encoding="utf-8")
    )
    assert code == 0
    assert manifest["files"]["hooks/demo.py"] == expected
    assert manifest["version"] == 1


def test_verify_passes_when_unchanged(isolated_repo: Path) -> None:
    # Arrange
    _write_hook(isolated_repo, "demo.py", "print('hello')\n")
    hook_integrity.update_baseline()

    # Act
    result = hook_integrity.verify_baseline()

    # Assert
    assert result == 0


def test_verify_detects_drift(
    isolated_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    path = _write_hook(isolated_repo, "demo.py", "print('hello')\n")
    hook_integrity.update_baseline()
    path.write_text("print('TAMPERED')\n", encoding="utf-8")

    # Act
    result = hook_integrity.verify_baseline()

    # Assert
    assert result == 2
    captured = capsys.readouterr()
    assert "MISMATCH" in captured.err


def test_assert_self_returns_false_on_drift(isolated_repo: Path) -> None:
    # Arrange
    path = _write_hook(isolated_repo, "demo.py", "print('hello')\n")
    hook_integrity.update_baseline()
    path.write_text("print('drift')\n", encoding="utf-8")

    # Act
    result = hook_integrity.assert_self(str(path))

    # Assert
    assert result is False


def test_assert_self_returns_true_when_clean(isolated_repo: Path) -> None:
    # Arrange
    path = _write_hook(isolated_repo, "demo.py", "print('hello')\n")
    hook_integrity.update_baseline()

    # Act
    result = hook_integrity.assert_self(str(path))

    # Assert
    assert result is True


def test_assert_self_returns_true_when_no_baseline(isolated_repo: Path) -> None:
    # Arrange
    path = _write_hook(isolated_repo, "demo.py", "x = 1\n")

    # Act
    result = hook_integrity.assert_self(str(path))

    # Assert
    assert result is True


def test_verify_emits_helpful_error_when_baseline_missing(
    isolated_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    manifest = isolated_repo / "hooks" / ".integrity.json"

    # Act
    code = hook_integrity.verify_baseline()

    # Assert
    captured = capsys.readouterr()
    assert manifest.exists() is False
    assert code == 1
    assert "No integrity manifest" in captured.err


def test_assert_self_skips_files_outside_repo(
    isolated_repo: Path, tmp_path: Path
) -> None:
    # Arrange
    outside = tmp_path / "outside.py"
    outside.write_text("# elsewhere\n", encoding="utf-8")

    # Act
    result = hook_integrity.assert_self(str(outside))

    # Assert
    assert result is True

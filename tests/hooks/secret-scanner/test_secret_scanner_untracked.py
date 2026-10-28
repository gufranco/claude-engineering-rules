from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / "secret-scanner.py"
FAKE_KEY = "AKIA" + "QWERTYUIOPASDFGH"


@pytest.fixture
def scanner() -> ModuleType:
    sys.path.insert(0, str(HOOK_PATH.parent))
    spec = importlib.util.spec_from_file_location("secret_scanner_units", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_listing_untracked_files_outside_a_repository_fails(scanner, tmp_path):
    # Arrange
    folder = tmp_path / "plain"
    folder.mkdir()

    # Act
    attempt = lambda: scanner._untracked_lines(str(folder), None)  # noqa: E731

    # Assert
    with pytest.raises(scanner.ScanError, match="git ls-files failed"):
        attempt()


def test_an_oversized_untracked_file_is_not_read(scanner, tmp_path):
    # Arrange
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=30)
    big = repo / "dump.txt"
    big.write_text(FAKE_KEY + "\n" + "x" * (scanner.MAX_UNTRACKED_BYTES + 1))
    (repo / "small.txt").write_text("hello\n", encoding="utf-8")

    # Act
    lines = scanner._untracked_lines(str(repo), None)

    # Assert
    assert lines == [("small.txt", 1, "hello\n")]

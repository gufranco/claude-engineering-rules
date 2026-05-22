"""Coverage for scripts/validate-markdown-links.py.

Exercises the shared detector through the validator entry point.
Source rule: rules/markdown-links.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate-markdown-links.py"


def run_validator(path: Path, *extra_args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path), *extra_args],
        capture_output=True,
        text=True,
        env=env,
        timeout=15.0,
        check=False,
    )


def test_clean_file_passes(tmp_path):
    # Arrange
    (tmp_path / "README.md").write_text("# Stub")
    target = tmp_path / "clean.md"
    target.write_text("# Clean\n\nSee [`README.md`](README.md) for details.\n")

    # Act
    proc = run_validator(target)

    # Assert
    assert proc.returncode == 0
    assert "PASSED" in proc.stdout


def test_bare_reference_to_existing_file_fails(tmp_path):
    # Arrange
    target = REPO_ROOT / "tmp-validator-test.md"
    target.write_text("# Bad\n\nLook at `README.md` for the project.\n")
    try:
        # Act
        proc = run_validator(target)

        # Assert
        assert proc.returncode == 1
        assert "FAILED" in proc.stdout
        assert "README.md" in proc.stdout
    finally:
        target.unlink(missing_ok=True)


def test_bare_reference_to_non_existing_file_passes(tmp_path):
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text("# Hypothetical\n\nImagine a `path/to/nowhere.md`.\n")

    # Act
    proc = run_validator(target)

    # Assert
    assert proc.returncode == 0


def test_fenced_code_block_is_skipped(tmp_path):
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text("# Code\n\n```\nrun on README.md\n```\n")

    # Act
    proc = run_validator(target)

    # Assert
    assert proc.returncode == 0


def test_link_text_is_not_flagged(tmp_path):
    # Arrange
    (tmp_path / "README.md").write_text("# Stub")
    target = tmp_path / "doc.md"
    target.write_text("# Link\n\nSee [`README.md`](README.md) for details.\n")

    # Act
    proc = run_validator(target)

    # Assert
    assert proc.returncode == 0


def test_short_tokens_ignored(tmp_path):
    """Tokens like ``.`` or single letters must never be flagged."""
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text("# Short\n\nRun `git add .` here.\n")

    # Act
    proc = run_validator(target)

    # Assert
    assert proc.returncode == 0


def test_repo_passes_validation():
    """The repo as a whole must pass after the link-discipline sweep."""
    # Arrange
    env = dict(os.environ)

    # Act
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASSED" in proc.stdout

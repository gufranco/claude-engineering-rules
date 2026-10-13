from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from faker import Faker

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / ".github" / "scripts" / "validate-markdown-links.py"


def run_validator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=30.0,
        check=False,
    )


SINGLE_FILE_PASS = (
    "PASSED: 0 blocking findings across 1 markdown files "
    "(bare references + broken link targets).\n"
)


def test_linked_reference_passes(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    (tmp_path / "README.md").write_text(f"# {faker.word()}\n")
    target = tmp_path / "clean.md"
    target.write_text(f"# {faker.word()}\n\nSee [`README.md`](README.md).\n")

    # Act
    proc = run_validator(str(target))

    # Assert
    assert (proc.returncode, proc.stdout) == (0, SINGLE_FILE_PASS)


def test_bare_reference_to_existing_file_fails(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    target = tmp_path / "bad.md"
    target.write_text(f"# {faker.word()}\n\nLook at `README.md` for the project.\n")

    # Act
    proc = run_validator(str(target))

    # Assert
    assert proc.returncode == 1
    assert proc.stdout.startswith("FAILED: 1 bare file reference(s) found\n")
    assert f"{target}:3:9: `README.md` -> existing file at " in proc.stdout


def test_bare_reference_to_non_existing_file_passes(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    target = tmp_path / "doc.md"
    missing = f"{faker.word()}/{faker.uuid4()}.md"
    target.write_text(f"# {faker.word()}\n\nImagine a `{missing}`.\n")

    # Act
    proc = run_validator(str(target))

    # Assert
    assert (proc.returncode, proc.stdout) == (0, SINGLE_FILE_PASS)


def test_fenced_code_block_is_skipped(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text(f"# {faker.word()}\n\n```\nrun on README.md\n```\n")

    # Act
    proc = run_validator(str(target))

    # Assert
    assert (proc.returncode, proc.stdout) == (0, SINGLE_FILE_PASS)


def test_short_tokens_ignored(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text(f"# {faker.word()}\n\nRun `git add .` here.\n")

    # Act
    proc = run_validator(str(target))

    # Assert
    assert (proc.returncode, proc.stdout) == (0, SINGLE_FILE_PASS)


def test_repo_passes_validation() -> None:
    # Arrange
    whole_repo_args: tuple[str, ...] = ()

    # Act
    proc = run_validator(*whole_repo_args)

    # Assert
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.startswith("PASSED: 0 blocking findings across ")

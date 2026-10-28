from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
FIX_SCRIPT_RELATIVE = Path(".github") / "scripts" / "fix-markdown-links.py"

Scratch = Callable[[str, str], Path]
FixRunner = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def run_fix(scratch_repo_root: Path) -> FixRunner:
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / FIX_SCRIPT_RELATIVE),
                "--root",
                str(scratch_repo_root),
                *args,
            ],
            capture_output=True,
            text=True,
            env=apply_coverage_env(dict(os.environ)),
            timeout=30.0,
            check=False,
        )

    return _run


def test_dry_run_does_not_modify_file(
    repo_scratch: Scratch, run_fix: FixRunner, faker: Faker
) -> None:
    # Arrange
    text = f"{faker.word()} `README.md` mention.\n"
    target = repo_scratch("dryrun.md", text)

    # Act
    proc = run_fix(str(target), "--dry-run")

    # Assert
    assert proc.returncode == 0
    assert target.read_text() == text
    assert "Would apply 1 fix(es) across 1 file(s) (dry run)." in proc.stdout


def test_fix_applies_wrapping(
    repo_scratch: Scratch, run_fix: FixRunner, faker: Faker
) -> None:
    # Arrange
    word = faker.word()
    target = repo_scratch("apply.md", f"Look at `README.md` for {word}.\n")

    # Act
    proc = run_fix(str(target))

    # Assert
    assert proc.returncode == 0
    assert target.read_text() == f"Look at [`README.md`](README.md) for {word}.\n"


def test_fix_is_idempotent(
    repo_scratch: Scratch, run_fix: FixRunner, faker: Faker
) -> None:
    # Arrange
    text = f"{faker.word()} [`README.md`](README.md) linked.\n"
    target = repo_scratch("idempotent.md", text)

    # Act
    proc = run_fix(str(target))

    # Assert
    assert proc.returncode == 0
    assert target.read_text() == text


def test_fix_skips_advisory_unless_flag(
    repo_scratch: Scratch, run_fix: FixRunner, faker: Faker
) -> None:
    # Arrange
    text = f"{faker.word()} `README.md` mention.\n"
    spec_target = repo_scratch("specs/advisory.md", text)

    # Act
    proc = run_fix(str(spec_target))

    # Assert
    assert proc.returncode == 0
    assert spec_target.read_text() == text


def test_fix_with_include_advisory_modifies_specs(
    repo_scratch: Scratch, run_fix: FixRunner, faker: Faker
) -> None:
    # Arrange
    word = faker.word()
    spec_target = repo_scratch("specs/include-advisory.md", f"{word} `README.md`.\n")

    # Act
    proc = run_fix(str(spec_target), "--include-advisory")

    # Assert
    assert proc.returncode == 0
    assert spec_target.read_text() == f"{word} [`README.md`](../README.md).\n"


def test_fix_rewrites_broken_target_to_file_relative(
    repo_scratch: Scratch, run_fix: FixRunner
) -> None:
    # Arrange
    subdir_target = repo_scratch("broken-subdir/doc.md", "See [home](README.md).\n")

    # Act
    proc = run_fix(str(subdir_target))

    # Assert
    assert proc.returncode == 0
    assert subdir_target.read_text() == "See [home](../README.md).\n"
    assert "rewrote 1 broken target(s) in broken-subdir/doc.md" in proc.stdout


def test_fix_dry_run_lists_broken_targets(
    repo_scratch: Scratch, run_fix: FixRunner
) -> None:
    # Arrange
    text = "See [home](README.md).\n"
    subdir_target = repo_scratch("dry-broken-subdir/doc.md", text)

    # Act
    proc = run_fix(str(subdir_target), "--dry-run")

    # Assert
    assert proc.returncode == 0
    assert subdir_target.read_text() == text
    assert "would rewrite 1 broken target(s) in dry-broken-subdir/doc.md" in (
        proc.stdout
    )


def test_fix_warns_on_unfixable_broken_target(
    repo_scratch: Scratch, run_fix: FixRunner, faker: Faker
) -> None:
    # Arrange
    text = f"See [ghost]({faker.uuid4()}.md).\n"
    target = repo_scratch("unfixable.md", text)

    # Act
    proc = run_fix(str(target))

    # Assert
    assert proc.returncode == 0
    assert target.read_text() == text
    assert "WARNING" in proc.stdout
    assert "manual review" in proc.stdout


def test_fix_preserves_fragment_when_rewriting_target(
    repo_scratch: Scratch, run_fix: FixRunner, faker: Faker
) -> None:
    # Arrange
    anchor = faker.word()
    subdir_target = repo_scratch(
        "fragment-subdir/doc.md", f"See [intro](README.md#{anchor}).\n"
    )

    # Act
    proc = run_fix(str(subdir_target))

    # Assert
    assert proc.returncode == 0
    assert subdir_target.read_text() == f"See [intro](../README.md#{anchor}).\n"

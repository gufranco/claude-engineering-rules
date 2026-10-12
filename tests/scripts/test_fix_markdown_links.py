from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIX_SCRIPT = REPO_ROOT / ".github" / "scripts" / "fix-markdown-links.py"
SUBPROCESS_COV_DIR = REPO_ROOT / "tests" / "_subprocess_cov"
COVERAGERC_PATH = REPO_ROOT / ".coveragerc"


def _coverage_active() -> bool:
    if "COVERAGE_PROCESS_START" in os.environ or "COVERAGE_RUN" in os.environ:
        return True
    if "pytest_cov" in sys.modules or "pytest_cov.plugin" in sys.modules:
        return True
    cov_module = sys.modules.get("coverage")
    if cov_module is None:
        return False
    current = getattr(cov_module, "Coverage", None)
    if current is None:
        return False
    return getattr(current, "current", lambda: None)() is not None


def run_fix(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if _coverage_active():
        env["COVERAGE_PROCESS_START"] = str(COVERAGERC_PATH)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{SUBPROCESS_COV_DIR}{os.pathsep}{existing_pp}"
            if existing_pp
            else str(SUBPROCESS_COV_DIR)
        )
    return subprocess.run(
        [sys.executable, str(FIX_SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30.0,
        check=False,
    )


def test_dry_run_does_not_modify_file(repo_scratch):
    # Arrange
    target = repo_scratch("tmp-fix-dryrun.md", "Bare `README.md` mention.\n")

    # Act
    proc = run_fix(str(target), "--dry-run")

    # Assert
    assert proc.returncode == 0
    assert target.read_text() == "Bare `README.md` mention.\n"
    assert "Would apply 1 fix(es) across 1 file(s) (dry run)." in proc.stdout


def test_fix_applies_wrapping(repo_scratch):
    # Arrange
    target = repo_scratch("tmp-fix-apply.md", "Look at `README.md` for details.\n")

    # Act
    proc = run_fix(str(target))

    # Assert
    assert proc.returncode == 0
    assert "[`README.md`](README.md)" in target.read_text()


def test_fix_is_idempotent(repo_scratch):
    # Arrange
    text = "Already [`README.md`](README.md) linked.\n"
    target = repo_scratch("tmp-fix-idempotent.md", text)

    # Act
    proc = run_fix(str(target))

    # Assert
    assert proc.returncode == 0
    assert target.read_text() == text


def test_fix_skips_advisory_unless_flag(repo_scratch):
    # Arrange
    text = "Bare `README.md` mention.\n"
    spec_target = repo_scratch("specs/tmp-fix-advisory.md", text)

    # Act
    proc = run_fix(str(spec_target))

    # Assert
    assert proc.returncode == 0
    assert spec_target.read_text() == text


def test_fix_with_include_advisory_modifies_specs(repo_scratch):
    # Arrange
    spec_target = repo_scratch(
        "specs/tmp-fix-include-advisory.md", "Bare `README.md` mention.\n"
    )

    # Act
    proc = run_fix(str(spec_target), "--include-advisory")

    # Assert
    assert proc.returncode == 0
    assert "[`README.md`](../README.md)" in spec_target.read_text()


def test_fix_rewrites_broken_target_to_file_relative(repo_scratch):
    # Arrange
    repo_scratch("tmp-fix-broken-target.md", "See [the spec](README.md).\n")
    subdir_target = repo_scratch(
        "tmp-fix-broken-subdir/doc.md", "See [home](README.md).\n"
    )

    # Act
    proc = run_fix(str(subdir_target))

    # Assert
    assert proc.returncode == 0
    assert "[home](../README.md)" in subdir_target.read_text()
    assert "rewrote 1 broken target" in proc.stdout


def test_fix_dry_run_lists_broken_targets(repo_scratch):
    # Arrange
    text = "See [home](README.md).\n"
    subdir_target = repo_scratch("tmp-fix-dry-broken-subdir/doc.md", text)

    # Act
    proc = run_fix(str(subdir_target), "--dry-run")

    # Assert
    assert proc.returncode == 0
    assert subdir_target.read_text() == text
    assert "would rewrite" in proc.stdout


def test_fix_warns_on_unfixable_broken_target(repo_scratch):
    # Arrange
    text = "See [ghost](truly-missing-file.md).\n"
    target = repo_scratch("tmp-fix-unfixable.md", text)

    # Act
    proc = run_fix(str(target))

    # Assert
    assert proc.returncode == 0
    assert target.read_text() == text
    assert "WARNING" in proc.stdout
    assert "manual review" in proc.stdout


def test_fix_preserves_fragment_when_rewriting_target(repo_scratch):
    # Arrange
    subdir_target = repo_scratch(
        "tmp-fix-fragment-subdir/doc.md", "See [intro](README.md#intro).\n"
    )

    # Act
    proc = run_fix(str(subdir_target))

    # Assert
    assert proc.returncode == 0
    assert "[intro](../README.md#intro)" in subdir_target.read_text()

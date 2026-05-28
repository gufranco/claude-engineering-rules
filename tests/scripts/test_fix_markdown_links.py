"""Tests for scripts/fix-markdown-links.py.

Exercises the auto-wrapper across happy paths, idempotency, dry-run
mode, and the advisory directory skip. Source rule: rules/markdown-links.md.
"""

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


def test_dry_run_does_not_modify_file(tmp_path):
    # Arrange
    target = REPO_ROOT / "tmp-fix-dryrun.md"
    target.write_text("Bare `README.md` mention.\n")
    try:
        # Act
        proc = run_fix(str(target), "--dry-run")
        # Assert
        assert proc.returncode == 0
        assert target.read_text() == "Bare `README.md` mention.\n"
        assert "would fix" in proc.stdout.lower() or "Would apply" in proc.stdout
    finally:
        target.unlink(missing_ok=True)


def test_fix_applies_wrapping():
    # Arrange
    target = REPO_ROOT / "tmp-fix-apply.md"
    target.write_text("Look at `README.md` for details.\n")
    try:
        # Act
        proc = run_fix(str(target))
        result = target.read_text()
        # Assert
        assert proc.returncode == 0
        assert "[`README.md`](README.md)" in result
    finally:
        target.unlink(missing_ok=True)


def test_fix_is_idempotent():
    # Arrange
    target = REPO_ROOT / "tmp-fix-idempotent.md"
    target.write_text("Already [`README.md`](README.md) linked.\n")
    try:
        # Act
        proc = run_fix(str(target))
        # Assert
        assert proc.returncode == 0
        assert target.read_text() == "Already [`README.md`](README.md) linked.\n"
    finally:
        target.unlink(missing_ok=True)


def test_fix_skips_advisory_unless_flag():
    # Arrange
    spec_target = REPO_ROOT / "specs" / "tmp-fix-advisory.md"
    spec_target.parent.mkdir(parents=True, exist_ok=True)
    spec_target.write_text("Bare `README.md` mention.\n")
    try:
        # Act
        proc = run_fix(str(spec_target))
        # Assert: advisory path left as-is
        assert proc.returncode == 0
        assert spec_target.read_text() == "Bare `README.md` mention.\n"
    finally:
        spec_target.unlink(missing_ok=True)


def test_fix_with_include_advisory_modifies_specs():
    # Arrange
    spec_target = REPO_ROOT / "specs" / "tmp-fix-include-advisory.md"
    spec_target.parent.mkdir(parents=True, exist_ok=True)
    spec_target.write_text("Bare `README.md` mention.\n")
    try:
        # Act
        proc = run_fix(str(spec_target), "--include-advisory")
        result = spec_target.read_text()
        # Assert: link target is file-relative (specs/foo.md to repo-root README.md)
        assert proc.returncode == 0
        assert "[`README.md`](../README.md)" in result
    finally:
        spec_target.unlink(missing_ok=True)


def test_fix_rewrites_broken_target_to_file_relative():
    # Arrange: link uses repo-root-relative path (the common GitHub-breaking mistake)
    target = REPO_ROOT / "tmp-fix-broken-target.md"
    target.write_text("See [the spec](README.md).\n")
    # Place the doc inside a subdirectory so a repo-root path needs rewriting.
    subdir = REPO_ROOT / "tmp-fix-broken-subdir"
    subdir.mkdir(exist_ok=True)
    subdir_target = subdir / "doc.md"
    subdir_target.write_text("See [home](README.md).\n")
    try:
        # Act
        proc = run_fix(str(subdir_target))
        result = subdir_target.read_text()
        # Assert
        assert proc.returncode == 0
        assert "[home](../README.md)" in result
        assert "rewrote 1 broken target" in proc.stdout
    finally:
        subdir_target.unlink(missing_ok=True)
        try:
            subdir.rmdir()
        except OSError:
            pass
        target.unlink(missing_ok=True)


def test_fix_dry_run_lists_broken_targets():
    # Arrange
    subdir = REPO_ROOT / "tmp-fix-dry-broken-subdir"
    subdir.mkdir(exist_ok=True)
    subdir_target = subdir / "doc.md"
    subdir_target.write_text("See [home](README.md).\n")
    original = subdir_target.read_text()
    try:
        # Act
        proc = run_fix(str(subdir_target), "--dry-run")
        # Assert: dry-run does not modify the file
        assert proc.returncode == 0
        assert subdir_target.read_text() == original
        assert "would rewrite" in proc.stdout
    finally:
        subdir_target.unlink(missing_ok=True)
        try:
            subdir.rmdir()
        except OSError:
            pass


def test_fix_warns_on_unfixable_broken_target():
    # Arrange: link target does not exist anywhere in the repo
    target = REPO_ROOT / "tmp-fix-unfixable.md"
    target.write_text("See [ghost](truly-missing-file.md).\n")
    original = target.read_text()
    try:
        # Act
        proc = run_fix(str(target))
        # Assert: file untouched, warning printed
        assert proc.returncode == 0
        assert target.read_text() == original
        assert "WARNING" in proc.stdout
        assert "manual review" in proc.stdout
    finally:
        target.unlink(missing_ok=True)


def test_fix_preserves_fragment_when_rewriting_target():
    # Arrange
    subdir = REPO_ROOT / "tmp-fix-fragment-subdir"
    subdir.mkdir(exist_ok=True)
    subdir_target = subdir / "doc.md"
    subdir_target.write_text("See [intro](README.md#intro).\n")
    try:
        # Act
        proc = run_fix(str(subdir_target))
        # Assert
        assert proc.returncode == 0
        assert "[intro](../README.md#intro)" in subdir_target.read_text()
    finally:
        subdir_target.unlink(missing_ok=True)
        try:
            subdir.rmdir()
        except OSError:
            pass

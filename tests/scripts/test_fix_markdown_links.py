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
FIX_SCRIPT = REPO_ROOT / "scripts" / "fix-markdown-links.py"
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
        # Assert
        assert proc.returncode == 0
        assert "[`README.md`](README.md)" in result
    finally:
        spec_target.unlink(missing_ok=True)

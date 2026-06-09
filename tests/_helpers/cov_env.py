"""Activate subprocess coverage for tests that shell out to hook scripts.

Mirrors the wiring in `tests/conftest.py::_build_env` so that test files
which call `subprocess.run([sys.executable, HOOK])` directly stitch their
subprocess coverage into the parent pytest-cov report.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
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
    coverage_cls = getattr(cov_module, "Coverage", None)
    if coverage_cls is None:
        return False
    current = getattr(coverage_cls, "current", lambda: None)
    return current() is not None


def apply_coverage_env(env: dict, *, force_active: bool | None = None) -> dict:
    """Return a copy of `env` with subprocess-coverage variables added when active.

    `force_active` is an override for tests of this helper.
    """
    active = _coverage_active() if force_active is None else force_active
    if not active:
        return dict(env)
    out = dict(env)
    out["COVERAGE_PROCESS_START"] = str(COVERAGERC_PATH)
    existing = out.get("PYTHONPATH", "")
    out["PYTHONPATH"] = (
        f"{SUBPROCESS_COV_DIR}{os.pathsep}{existing}"
        if existing
        else str(SUBPROCESS_COV_DIR)
    )
    out["COVERAGE_FILE"] = str(REPO_ROOT / ".coverage")
    # Python 3.12+ defaults to the `sysmon` core which silently records zero
    # line hits for some subprocess Python scripts. Force the C tracer so
    # subprocess coverage is deterministic.
    out.setdefault("COVERAGE_CORE", "ctrace")
    return out

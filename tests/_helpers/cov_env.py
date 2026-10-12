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
    active = _coverage_active() if force_active is None else force_active
    out = dict(env)
    out["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    if not active:
        return out
    out["COVERAGE_PROCESS_START"] = str(COVERAGERC_PATH)
    out["CLAUDE_COVERAGE_ROOT"] = str(REPO_ROOT)
    existing = out.get("PYTHONPATH", "")
    out["PYTHONPATH"] = (
        f"{SUBPROCESS_COV_DIR}{os.pathsep}{existing}"
        if existing
        else str(SUBPROCESS_COV_DIR)
    )
    out["COVERAGE_FILE"] = str(REPO_ROOT / ".coverage")
    out.setdefault("COVERAGE_CORE", "ctrace")
    return out

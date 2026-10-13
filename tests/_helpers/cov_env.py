from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUBPROCESS_COV_DIR = REPO_ROOT / "tests" / "_subprocess_cov"
COVERAGERC_PATH = REPO_ROOT / ".coveragerc"
EMPTY_BYPASS_REGISTRY = os.devnull
BYPASS_STATE_VAR = "CLAUDE_BYPASS_STATE"
AUDIT_DISABLE_VAR = "CLAUDE_HOOK_AUDIT_DISABLE"


def coverage_active() -> bool:
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


def _with_subprocess_coverage(env: dict[str, str]) -> dict[str, str]:
    existing = env.get("PYTHONPATH", "")
    pythonpath = (
        f"{SUBPROCESS_COV_DIR}{os.pathsep}{existing}"
        if existing
        else str(SUBPROCESS_COV_DIR)
    )
    return {
        "COVERAGE_FILE": str(REPO_ROOT / ".coverage"),
        "COVERAGE_CORE": "ctrace",
        **env,
        "COVERAGE_PROCESS_START": str(COVERAGERC_PATH),
        "CLAUDE_COVERAGE_ROOT": str(REPO_ROOT),
        "PYTHONPATH": pythonpath,
    }


def apply_coverage_env(
    env: Mapping[str, str], *, force_active: bool | None = None
) -> dict[str, str]:
    active = coverage_active() if force_active is None else force_active
    isolated = {
        AUDIT_DISABLE_VAR: "1",
        BYPASS_STATE_VAR: EMPTY_BYPASS_REGISTRY,
        **env,
    }
    if not active:
        return isolated
    return _with_subprocess_coverage(isolated)

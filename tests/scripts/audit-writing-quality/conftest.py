from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "audit-writing-quality.py"


@pytest.fixture(scope="module")
def audit_mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location("audit_writing_quality", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audit_writing_quality"] = mod
    spec.loader.exec_module(mod)
    return mod

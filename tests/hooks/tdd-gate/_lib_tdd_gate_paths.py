"""Shared-temp-root constant read from the hook under test."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[3] / "hooks" / "tdd-gate.py"
_spec = importlib.util.spec_from_file_location("_tdd_gate_hook_for_paths", _HOOK)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load hook module at {_HOOK}")
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

SHARED_TEMP_ROOTS: tuple[Path, ...] = _module.SHARED_TEMP_ROOTS

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

HOOK_SOURCE = (
    Path(__file__).resolve().parents[3] / "hooks" / "dangerous-command-blocker.py"
)


def load_module() -> ModuleType:
    if str(HOOK_SOURCE.parent) not in sys.path:
        sys.path.insert(0, str(HOOK_SOURCE.parent))
    spec = importlib.util.spec_from_file_location(
        "dangerous_command_blocker", HOOK_SOURCE
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {HOOK_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

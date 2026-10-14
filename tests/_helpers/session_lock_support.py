from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.session_lock import (  # noqa: E402
    DEFAULT_TTL_SECONDS,
    MAX_TTL_SECONDS,
    MIN_TTL_SECONDS,
    WILDCARD,
    acquire,
    is_locked,
    release,
)
import _lib.session_lock as module  # noqa: E402


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "MAX_TTL_SECONDS",
    "MIN_TTL_SECONDS",
    "ROOT",
    "WILDCARD",
    "acquire",
    "is_locked",
    "module",
    "release",
]

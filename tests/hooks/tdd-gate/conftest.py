from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from _lib_tdd_gate_paths import SHARED_TEMP_ROOTS


def _base_outside_shared_temp_roots() -> Path:
    base = Path.home() / ".cache" / "claude-hook-tests" / "tdd-gate"
    base.mkdir(parents=True, exist_ok=True)
    resolved = base.resolve()
    for root in SHARED_TEMP_ROOTS:
        if resolved.is_relative_to(root):
            raise RuntimeError(
                f"temp base {resolved} is inside shared temp root {root}; "
                "the tdd-gate suite cannot exercise its blocking path there"
            )
    return resolved


@pytest.fixture(scope="session")
def tdd_gate_temp_base() -> Iterator[Path]:
    base = Path(tempfile.mkdtemp(dir=_base_outside_shared_temp_roots()))
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def tmp_path(tdd_gate_temp_base: Path) -> Iterator[Path]:
    created = Path(tempfile.mkdtemp(dir=tdd_gate_temp_base))
    try:
        yield created
    finally:
        shutil.rmtree(created, ignore_errors=True)

"""Temp-path override for the tdd-gate suite.

The hook exempts shared temp roots, `/tmp` and `/private/tmp`, because
files there are throwaway by construction. It deliberately does not exempt
the per-user TMPDIR, so that its own tests still exercise the blocking
path.

That holds on macOS, where pytest's `tmp_path` lives under `/var/folders`.
On Linux `tmp_path` lives under `/tmp/pytest-of-<user>`, which is inside a
shared root, so every blocking test silently turned into an allow. These
fixtures give the suite a base outside both shared roots on either
platform, which is what keeps the assertions meaningful everywhere.
"""

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
    base = _base_outside_shared_temp_roots()
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

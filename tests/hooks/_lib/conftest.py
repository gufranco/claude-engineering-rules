from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def state_path(tmp_path: Path) -> Path:
    return tmp_path / ".session-locks.json"

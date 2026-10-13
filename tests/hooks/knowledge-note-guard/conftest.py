from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for sub in (
        "wiki/concepts",
        "wiki/entities",
        "raw/articles",
        "daily",
        "templates",
        "_trash",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def env(vault: Path) -> dict[str, str]:
    return {"SECOND_BRAIN_VAULT": str(vault)}

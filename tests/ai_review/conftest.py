from __future__ import annotations

from pathlib import Path

import pytest
from faker import Faker

from _helpers.ai_review_support import (
    login,
)


@pytest.fixture
def account(faker: Faker) -> str:
    return login(faker)


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "profiles.json"

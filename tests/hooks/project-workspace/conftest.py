from __future__ import annotations

import pytest
from _ppw_support import (
    GIT_ENV,
)


@pytest.fixture(autouse=True)
def isolated_git_config(monkeypatch):
    for key, value in GIT_ENV.items():
        monkeypatch.setenv(key, value)

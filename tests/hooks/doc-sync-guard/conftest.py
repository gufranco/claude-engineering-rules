from __future__ import annotations

from pathlib import Path

import pytest
from doc_sync_guard_test_repo import (
    _git,
)
from faker import Faker


@pytest.fixture()
def repo(tmp_path: Path, faker: Faker) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", faker.email())
    _git(root, "config", "user.name", faker.first_name())
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "commit", "--allow-empty", "-qm", "chore: root")
    return root

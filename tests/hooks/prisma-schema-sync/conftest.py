from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def unreadable_schema(tmp_path: Path) -> Iterator[Path]:
    prisma_dir = tmp_path / "prisma"
    prisma_dir.mkdir()
    schema = prisma_dir / "schema.prisma"
    schema.write_text("model Game {\n  id String @id\n}\n", encoding="utf-8")
    schema.chmod(0o000)
    migrations_dir = prisma_dir / "migrations" / "20260101000000_init"
    migrations_dir.mkdir(parents=True)
    yield migrations_dir / "migration.sql"
    schema.chmod(0o644)

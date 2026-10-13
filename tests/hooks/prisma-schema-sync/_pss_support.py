from __future__ import annotations

from pathlib import Path

HOOK = "prisma-schema-sync"
MATCHING_SCHEMA = (
    "model Game {\n"
    "  id String @id\n"
    "  homeTeam String\n"
    "  awayTeam String\n"
    '  @@index([homeTeam], map: "Game_homeTeam_idx")\n'
    '  @@unique([awayTeam], map: "Game_awayTeam_key")\n'
    "}\n"
)
MATCHING_MIGRATION = (
    'CREATE TABLE "Game" ("id" TEXT NOT NULL, "homeTeam" TEXT NOT NULL, "awayTeam" TEXT NOT NULL);\n'
    'CREATE INDEX "Game_homeTeam_idx" ON "Game" ("homeTeam");\n'
    'CREATE UNIQUE INDEX "Game_awayTeam_key" ON "Game" ("awayTeam");\n'
)


def _write_schema(tmp_path: Path, body: str) -> Path:
    prisma_dir = tmp_path / "prisma"
    prisma_dir.mkdir(parents=True, exist_ok=True)
    schema = prisma_dir / "schema.prisma"
    schema.write_text(body, encoding="utf-8")
    migrations_dir = prisma_dir / "migrations" / "20260101000000_init"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    return migrations_dir / "migration.sql"

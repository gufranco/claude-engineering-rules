from __future__ import annotations

from pathlib import Path

from _helpers.hook_assertions import assert_blocked

HOOK = "prisma-schema-sync"


def drifted_migration(tmp_path: Path) -> Path:
    prisma_dir = tmp_path / "prisma"
    migrations_dir = prisma_dir / "migrations" / "20260101000000_init"
    migrations_dir.mkdir(parents=True)
    (prisma_dir / "schema.prisma").write_text(
        "model Game {\n  id String @id\n  homeTeam String\n}\n", encoding="utf-8"
    )
    return migrations_dir / "migration.sql"


def test_block_message_routes_the_bypass_reason_away_from_migration_comments(
    tmp_path, tool_use, run_hook
):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": str(drifted_migration(tmp_path)),
            "content": 'CREATE INDEX "Game_homeTeam_idx" ON "Game" ("homeTeam");\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, "pull request description or an ADR")
    assert "~/.claude/rules/lang/orm-migrations.md" in stderr
    assert "leading comment" not in stderr

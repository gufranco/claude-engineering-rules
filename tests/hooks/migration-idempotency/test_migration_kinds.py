from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "migration-idempotency"
PATH = "/repo/prisma/migrations/20261013000000_x/migration.sql"


def _write(tool_use, sql: str):
    return tool_use("Write", {"file_path": PATH, "content": sql})


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE OR REPLACE FUNCTION f() RETURNS int AS $$ SELECT 1 $$ LANGUAGE sql;",
        "CREATE OR REPLACE VIEW v AS SELECT 1;",
        "CREATE OR REPLACE TRIGGER t AFTER INSERT ON a FOR EACH ROW EXECUTE FUNCTION f();",
        "DO $$ BEGIN\n"
        "  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mood') THEN\n"
        "    CREATE TYPE mood AS ENUM ('ok');\n"
        "  END IF;\n"
        "END $$;",
        "DO $guard$ BEGIN\n"
        "  CREATE POLICY p ON a USING (true);\n"
        "EXCEPTION WHEN duplicate_object THEN NULL;\n"
        "END $guard$;",
    ],
    ids=["function", "view", "trigger", "type-in-do", "policy-in-do"],
)
def test_the_idempotent_form_for_each_kind_is_allowed(tool_use, run_hook, sql):
    # Arrange
    payload = _write(tool_use, sql)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("CREATE VIEW v AS SELECT 1;", "CREATE VIEW without OR REPLACE"),
        (
            "CREATE FUNCTION f() RETURNS int AS $$ SELECT 1 $$ LANGUAGE sql;",
            "CREATE FUNCTION without OR REPLACE",
        ),
        ("CREATE TYPE mood AS ENUM ('ok');", "CREATE TYPE outside a guarded DO block"),
        ("CREATE ROLE reader;", "CREATE ROLE outside a guarded DO block"),
        (
            "DO $$ BEGIN CREATE TYPE mood AS ENUM ('ok'); END $$;",
            "CREATE TYPE outside a guarded DO block",
        ),
    ],
    ids=["view", "function", "type", "role", "unguarded-do"],
)
def test_a_form_that_fails_on_rerun_is_blocked(tool_use, run_hook, sql, reason):
    # Arrange
    payload = _write(tool_use, sql)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, reason)

from __future__ import annotations

import json

import pytest

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "polyglot-immutability-guard"

BLOCKED: list[tuple[str, str, str]] = [
    (
        "/repo/cmd/main.go",
        "var seen = map[string]bool{}\n\nfunc mark(id string) {\n\tseen[id] = true\n}\n",
        "`seen`",
    ),
    ("/repo/src/lib.rs", "static mut COUNT: u32 = 0;\n", "`static mut`"),
    ("/repo/src/A.java", "class A {\n    public static int count = 0;\n}\n", "`count`"),
    ("/repo/src/A.kt", "data class User(var name: String)\n", "`User`"),
    (
        "/repo/src/A.cs",
        "public record struct Point(int X);\n",
        "readonly record struct",
    ),
    (
        "/repo/lib/card.dart",
        "class Card extends StatelessWidget {\n  String title;\n}\n",
        "`title`",
    ),
    ("/repo/lib/a.rb", "# frozen_string_literal: true\n\nROLES = [:a]\n", "`ROLES`"),
    ("/repo/src/tables.c", "u8 palette[2] = {1, 2};\n", "`palette`"),
]

SKIPPED_PATHS: list[str] = [
    "/repo/cmd/main_test.go",
    "/repo/src/test/java/ATest.java",
    "/repo/spec/models/user_spec.rb",
    "/repo/lib/card.g.dart",
    "/repo/vendor/lib/a.go",
    "/repo/src/index.ts",
]


@pytest.mark.parametrize(("path", "content", "expected"), BLOCKED)
def test_blocks_mutable_state(tool_use, run_hook, path, content, expected):
    # Arrange
    payload = tool_use("Write", {"file_path": path, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, expected)


@pytest.mark.parametrize("path", SKIPPED_PATHS)
def test_skips_tests_generated_and_foreign_files(tool_use, run_hook, path):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": path,
            "content": "static mut X: u8 = 0;\nvar seen = map[string]bool{}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_advisory_finding_warns_without_blocking(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/cache.rs",
            "old_string": "a",
            "new_string": "cache: RefCell<Vec<u8>>,\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "interior mutability" in context


def test_disable_env_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/src/lib.rs", "content": "static mut X: u8 = 0;\n"}
    )

    # Act
    result = run_hook(HOOK, payload, env={"POLYGLOT_IMMUTABILITY_DISABLE": "1"})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_blocks_a_payload_that_is_not_an_object(run_hook):
    # Arrange
    command = "not-json"

    # Act
    result = run_hook(HOOK, command)

    # Assert
    assert_blocked(result, "could not read its input")

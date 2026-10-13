from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from comment_blocker_test_data import (
    BLOCK_MSG,
    HOOK,
)


@pytest.mark.parametrize("marker", ["// Act / Assert", "// Arrange / Act"])
def test_blocks_a_combined_marker_in_test_file(tool_use, run_hook, marker):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.test.ts", "content": f"{marker}\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert f"L1: {marker}" in stderr


@pytest.mark.parametrize("marker", ["// Arrange", "// Act", "// Assert"])
def test_allows_a_bare_marker_in_test_file(tool_use, run_hook, marker):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.test.ts", "content": f"{marker}\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_bare_marker_outside_a_test_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "// Arrange\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "L1: // Arrange" in stderr


def test_blocks_former_aaa_hash_marker_in_python_test(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/tests/test_x.py",
            "content": "# Arrange\nx = 1\n# Act / Assert\nassert x\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_prose_comment_in_test_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.test.ts",
            "content": "// setup the thing\nconst x = 1\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_marker_with_description_in_test_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.test.ts",
            "content": "// Act: do the thing\nconst x = 1\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_no_per_line_suppression_marker(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// allow-comment -- vendor banner\nconst x = 1\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_no_file_level_suppression_marker(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// @allow-comment -- legal header\n// legal line\nconst x = 1\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


@pytest.mark.parametrize(
    ("file_path", "content"),
    [
        ("/repo/src/app.ts", "// eslint-disable-next-line\nconst x = 1\n"),
        (
            "/repo/src/app.ts",
            "// eslint-disable-next-line no-console -- CLI entry point\nconst x = 1\n",
        ),
        ("/repo/src/app.ts", "/* eslint-disable no-console */\nconst x = 1\n"),
        ("/repo/src/app.ts", "// prettier-ignore\nconst x = 1\n"),
        ("/repo/src/app.ts", "// @ts-expect-error\nconst x = 1\n"),
        ("/repo/src/app.ts", "/** @ts-check */\nconst x = 1\n"),
        ("/repo/src/app.ts", '/// <reference types="node" />\nconst x = 1\n'),
        ("/repo/src/app.ts", "const x = 1 // eslint-disable-line no-magic-numbers\n"),
        ("/repo/src/app.ts", "// biome-ignore lint: intentional\nconst x = 1\n"),
        ("/repo/src/app.ts", "// istanbul ignore next\nconst x = 1\n"),
        ("/repo/pkg/main.go", "//go:build linux\n\npackage main\n"),
        ("/repo/pkg/main.go", "//nolint:errcheck\nx := 1\n"),
        ("/repo/src/app.py", "import os  # noqa: F401\n"),
        ("/repo/src/app.py", "x = load()  # type: ignore[no-any-return]\n"),
        ("/repo/src/app.py", "def f():\n    return 1  # pragma: no cover\n"),
        ("/repo/src/app.py", "# ruff: noqa: E501\nx = 1\n"),
        ("/repo/src/app.py", "# fmt: off\nx = 1\n# fmt: on\n"),
        ("/repo/src/app.py", "# pylint: disable=too-many-locals\nx = 1\n"),
        ("/repo/scripts/run.sh", "# shellcheck disable=SC2086\necho $x\n"),
        ("/repo/src/lib.rs", "// SAFETY: ptr is non-null and aligned\nunsafe { *p }\n"),
        ("/repo/src/app.ts", "// SPDX-License-Identifier: Apache-2.0\nconst x = 1\n"),
        ("/repo/src/app.py", "# SPDX-FileCopyrightText: 2026 Example\nx = 1\n"),
    ],
)
def test_allows_tool_directive(tool_use, run_hook, file_path, content):
    # Arrange
    payload = tool_use("Write", {"file_path": file_path, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "content",
    [
        "// eslint is configured to allow this\nconst x = 1\n",
        "// we disable eslint here because the rule is wrong\nconst x = 1\n",
        "// noqa was removed from the python side\nconst x = 1\n",
    ],
)
def test_blocks_prose_that_mentions_a_tool(tool_use, run_hook, content):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/src/app.ts", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_prose_continuation_of_directive_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "/* eslint-disable\n   because the rule is wrong here\n*/\nconst x = 1\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)

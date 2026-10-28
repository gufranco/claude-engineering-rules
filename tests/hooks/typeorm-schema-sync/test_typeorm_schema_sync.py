from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _typeorm_schema_sync_helpers import HOOK


def test_blocks_synchronize_true_in_data_source(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/data-source.ts",
            "content": (
                "import { DataSource } from 'typeorm';\n"
                "export const dataSource = new DataSource({\n"
                "  type: 'postgres',\n"
                "  synchronize: true,\n"
                "});\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "synchronize: true")


def test_blocks_drop_schema_true(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/data-source.ts",
            "old_string": "type: 'postgres',",
            "new_string": "type: 'postgres', dropSchema: true,",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "dropSchema: true")


def test_blocks_dataSource_synchronize_call(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/bootstrap.ts",
            "content": (
                "import { dataSource } from './data-source';\n"
                "await dataSource.synchronize();\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "dataSource.synchronize")


def test_blocks_dataSource_dropDatabase_call(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/bootstrap.ts",
            "edits": [
                {
                    "old_string": "await dataSource.initialize();",
                    "new_string": "await dataSource.initialize();\nawait dataSource.dropDatabase();",
                },
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "dropDatabase")


def test_allows_synchronize_false(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/data-source.ts",
            "content": (
                "import { DataSource } from 'typeorm';\n"
                "export const dataSource = new DataSource({\n"
                "  type: 'postgres',\n"
                "  synchronize: false,\n"
                "});\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def _typeorm_module():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "hooks" / "typeorm-schema-sync.py"
    spec = importlib.util.spec_from_file_location("typeorm_units", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("args", "expected"), [("f(a, b)", False), ("f(a), b", True)])
def test_has_top_level_comma_ignores_commas_inside_brackets(args, expected):
    # Arrange
    module = _typeorm_module()

    # Act
    result = module.has_top_level_comma(args)

    # Assert
    assert result is expected

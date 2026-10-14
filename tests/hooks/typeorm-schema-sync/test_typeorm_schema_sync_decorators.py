from __future__ import annotations
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _typeorm_schema_sync_helpers import HOOK


def test_blocks_index_decorator_without_name(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/game.entity.ts",
            "content": (
                "@Entity('game')\n"
                "@Index(['homeTeam', 'awayTeam'])\n"
                "export class Game {}\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "@Index")


def test_blocks_unique_decorator_without_name(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/user.entity.ts",
            "content": ("@Entity('user')\n@Unique(['email'])\nexport class User {}\n"),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "@Unique")


def test_blocks_check_decorator_without_name(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/order.entity.ts",
            "content": (
                "@Entity('order')\n@Check('amount > 0')\nexport class Order {}\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "@Check")


def test_allows_index_decorator_with_name(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/game.entity.ts",
            "content": (
                "@Entity('game')\n"
                "@Index('Game_homeTeam_idx', ['homeTeam'])\n"
                "export class Game {}\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_index_decorator_with_empty_args_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/x.entity.ts",
            "content": "@Index()\nexport class X {}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "@Index")


def test_check_decorator_with_empty_args_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/x.entity.ts",
            "content": "@Check()\nexport class X {}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "@Check")


def test_check_decorator_with_brackets_in_single_arg_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/x.entity.ts",
            "content": "@Check('amount + (tax * 2) > 0')\nexport class X {}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "@Check")


def test_check_decorator_with_two_args_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/x.entity.ts",
            "content": (
                "@Entity('order')\n"
                "@Check('Order_amount_chk', 'amount > 0')\n"
                "export class Order {}\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_index_with_object_first_arg_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entity.ts",
            "content": "@Index({ name: 'x' }, ['col'])\nexport class E {}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "@Index")

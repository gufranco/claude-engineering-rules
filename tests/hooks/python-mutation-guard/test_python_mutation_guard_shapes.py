from __future__ import annotations

import json

import pytest

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pmg_support import HOOK

BLOCKED_SHAPES: list[tuple[str, str, str]] = [
    (
        "nested-method",
        "def tag(order: Order, tag: str) -> None:\n    order.tags.append(tag)\n",
        "parameter `order` is mutated",
    ),
    (
        "in-place-plus",
        "def extend(items: list[str], more: list[str]) -> list[str]:\n    items += more\n    return items\n",
        "parameter `items` is mutated",
    ),
    (
        "nested-item",
        "def poke(memory: Memory, at: int) -> None:\n    memory.ram[at] = 0\n",
        "parameter `memory` is mutated",
    ),
    (
        "frozen-escape",
        "def touch(point: Point) -> None:\n    object.__setattr__(point, 'x', 1)\n",
        "object.__setattr__",
    ),
    (
        "global-rebind",
        "COUNT = 0\n\ndef bump() -> None:\n    global COUNT\n    COUNT = COUNT + 1\n",
        "global `COUNT`",
    ),
    (
        "module-state",
        "SEEN: dict[str, int] = {}\n\ndef record(key: str) -> None:\n    SEEN[key] = 1\n",
        "module-level `SEEN`",
    ),
    (
        "class-attribute",
        "class Registry:\n    handlers: list[str] = []\n",
        "mutable class attribute `handlers`",
    ),
]

ALLOWED_SHAPES: list[tuple[str, str]] = [
    (
        "rebound-copy",
        "def tag(items: list[str], tag: str) -> list[str]:\n    items = list(items)\n    items.append(tag)\n    return items\n",
    ),
    (
        "int-plus",
        "def bump(count: int) -> int:\n    count += 1\n    return count\n",
    ),
    (
        "post-init-escape",
        "class Point:\n    def __post_init__(self) -> None:\n        object.__setattr__(self, 'x', 1)\n",
    ),
    (
        "classvar",
        "from typing import ClassVar\n\nclass Registry:\n    handlers: ClassVar[tuple[str, ...]] = ()\n",
    ),
    (
        "pydantic-default",
        "class Body(BaseModel):\n    tags: list[str] = []\n",
    ),
    (
        "frozen-dataclass",
        "@dataclass(frozen=True, slots=True)\nclass Point:\n    x: int\n",
    ),
]


@pytest.mark.parametrize(("label", "content", "expected"), BLOCKED_SHAPES)
def test_blocks_mutation_shape(tool_use, run_hook, label, content, expected):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/app/core.py", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, expected)


@pytest.mark.parametrize(("label", "content"), ALLOWED_SHAPES)
def test_allows_non_mutating_shape(tool_use, run_hook, label, content):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/app/core.py", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_mutable_dataclass_is_advisory(tool_use, run_hook):
    # Arrange
    content = "@dataclass\nclass Point:\n    x: int\n"
    payload = tool_use("Write", {"file_path": "/repo/app/core.py", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "without `frozen=True`" in context


def test_parses_an_indented_edit_fragment(tool_use, run_hook):
    # Arrange
    fragment = (
        "    def add(self, items: list[str]) -> None:\n        items.append('x')\n"
    )
    payload = tool_use(
        "Edit",
        {"file_path": "/repo/app/core.py", "old_string": "a", "new_string": fragment},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "parameter `items` is mutated")


def test_skips_dotted_test_files(tool_use, run_hook):
    # Arrange
    content = "def stamp(image: bytearray) -> None:\n    image[0] = 1\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/tools/verify.test.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


ADVISORY_SHAPES: list[tuple[str, str]] = [
    (
        "attribute-write",
        "def rename(user: User, name: str) -> User:\n    user.name = name\n    return user\n",
    ),
    ("nested-attribute", "def step(cpu: Cpu) -> None:\n    cpu.registers.de = 0\n"),
    ("augmented-attribute", "def tick(voice: Voice) -> None:\n    voice.offset += 2\n"),
    (
        "setattr",
        "def patch(target: object, key: str) -> None:\n    setattr(target, key, 1)\n",
    ),
]


@pytest.mark.parametrize(("label", "content"), ADVISORY_SHAPES)
def test_attribute_writes_on_a_parameter_are_advisory(
    tool_use, run_hook, label, content
):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/app/core.py", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "(advisory)" in context

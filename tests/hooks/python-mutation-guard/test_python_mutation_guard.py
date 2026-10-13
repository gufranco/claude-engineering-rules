from __future__ import annotations

import json

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pmg_support import (
    ENFORCE,
    HOOK,
    PARAM_MUTATION,
)


def test_blocks_parameter_mutation(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": PARAM_MUTATION}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    _code, stderr = assert_blocked(result, "parameter `items` is mutated")
    assert "BLOCKED by python-mutation-guard" in stderr
    assert "L2" in stderr


def test_warns_without_blocking_by_default(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": PARAM_MUTATION}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert (
        "INFO from python-mutation-guard" in context,
        "PYTHON_MUTATION_ENFORCE=1" in context,
    ) == (True, True)


def test_blocks_mutable_default_list(tool_use, run_hook):
    # Arrange
    content = "def collect(items: list[str] = []) -> list[str]:\n    return items\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/collect.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(result, "mutable default")


def test_blocks_mutable_default_dict_call(tool_use, run_hook):
    # Arrange
    content = "def build(options=dict()):\n    return options\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/build.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(result, "mutable default")


def test_blocks_item_assignment_on_a_parameter(tool_use, run_hook):
    # Arrange
    content = (
        "def annotate(payload: dict[str, str], key: str) -> dict[str, str]:\n"
        "    payload[key] = 'seen'\n"
        "    return payload\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/annotate.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(result, "parameter `payload` is mutated")


def test_blocks_mutation_of_a_read_only_annotation(tool_use, run_hook):
    # Arrange
    content = (
        "from collections.abc import Sequence\n"
        "\n"
        "def rotate(values: Sequence[int]) -> None:\n"
        "    values.append(0)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/rotate.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    _code, stderr = assert_blocked(result, "parameter `values` is mutated")
    assert "Sequence" in stderr


def test_allows_a_fresh_list(tool_use, run_hook):
    # Arrange
    content = (
        "from collections.abc import Sequence\n"
        "\n"
        "def add_tag(items: Sequence[str], tag: str) -> tuple[str, ...]:\n"
        "    return (*items, tag)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_allows_mutation_of_a_local_accumulator(tool_use, run_hook):
    # Arrange
    content = (
        "def summarize(rows: tuple[Row, ...]) -> dict[str, int]:\n"
        "    totals: dict[str, int] = {}\n"
        "    for row in rows:\n"
        "        totals[row.key] = totals.get(row.key, 0) + row.value\n"
        "    return totals\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/summary.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_allows_none_default(tool_use, run_hook):
    # Arrange
    content = (
        "def collect(items: list[str] | None = None) -> list[str]:\n"
        "    return list(items or [])\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/collect.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_allows_self_mutation_in_a_method(tool_use, run_hook):
    # Arrange
    content = (
        "class Counter:\n"
        "    def __init__(self) -> None:\n"
        "        self._values: dict[str, int] = {}\n"
        "\n"
        "    def record(self, key: str) -> None:\n"
        "        self._values[key] = self._values.get(key, 0) + 1\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/counter.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_reports_every_offending_parameter(tool_use, run_hook):
    # Arrange
    content = (
        "def merge(left: list[int], right: list[int]) -> list[int]:\n"
        "    left.extend(right)\n"
        "    right.sort()\n"
        "    return left\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/merge.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    _code, stderr = assert_blocked(result, "parameter `left` is mutated")
    assert "parameter `right` is mutated" in stderr


def test_flags_edits_with_a_parsable_fragment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/app/services/tags.py",
            "old_string": "noop",
            "new_string": PARAM_MUTATION,
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(result, "parameter `items` is mutated")


def test_falls_back_to_regex_on_unparsable_fragments(tool_use, run_hook):
    # Arrange
    fragment = "    def helper(cache={}):\n        return cache\n"
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/app/services/helper.py",
            "old_string": "noop",
            "new_string": fragment,
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(result, "mutable default")


def test_skips_non_python_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/src/index.ts", "content": PARAM_MUTATION}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_skips_test_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/tests/test_tags.py", "content": PARAM_MUTATION}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_disable_env_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": PARAM_MUTATION}
    )

    # Act
    result = run_hook(HOOK, payload, env={"PYTHON_MUTATION_DISABLE": "1", **ENFORCE})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_ignores_unrelated_tools(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "true"})

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_blocks_a_payload_that_is_not_an_object(run_hook):
    # Arrange
    command = "not-json"

    # Act
    result = run_hook(HOOK, command)

    # Assert
    assert_blocked(result, "could not read its input")

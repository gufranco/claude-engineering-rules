from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pmg_support import (
    HOOK,
    PARAM_MUTATION,
)


def test_skips_stub_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.pyi", "content": PARAM_MUTATION}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_files_named_with_the_test_prefix(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/app/test_helpers.py", "content": PARAM_MUTATION}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_flags_multiedit_fragments(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/app/services/tags.py",
            "edits": [
                {"old_string": "a", "new_string": "X = 1\n"},
                {"old_string": "b", "new_string": PARAM_MUTATION},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "parameter `items` is mutated")


def test_reads_dotted_annotations(tool_use, run_hook):
    # Arrange
    content = (
        "import collections.abc\n"
        "\n"
        "def rotate(values: collections.abc.Sequence[int]) -> None:\n"
        "    values.append(0)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/rotate.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "parameter `values` is mutated")
    assert "Sequence" in stderr


def test_handles_unnamed_annotation_forms(tool_use, run_hook):
    # Arrange
    content = (
        "def apply(handlers: list['Handler'], item: object) -> None:\n"
        "    handlers.append(item)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/apply.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "parameter `handlers` is mutated")


def test_flags_mutation_of_varargs_and_kwargs(tool_use, run_hook):
    # Arrange
    content = (
        "def gather(*rows: dict[str, int], **options: str) -> None:\n"
        "    rows.append({})\n"
        "    options.update({'a': 'b'})\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/gather.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "parameter `rows` is mutated")
    assert "parameter `options` is mutated" in stderr


def test_flags_del_on_a_parameter_key(tool_use, run_hook):
    # Arrange
    content = (
        "def strip_secret(payload: dict[str, str]) -> dict[str, str]:\n"
        "    del payload['secret']\n"
        "    return payload\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/strip.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "parameter `payload` is mutated")


def test_honors_a_suppression_directive_on_the_mutation(tool_use, run_hook):
    # Arrange
    content = (
        "def add_tag(items: list[str], tag: str) -> list[str]:\n"
        "    # type: ignore[misc]\n"
        "    items.append(tag)\n"
        "    return items\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_honors_a_suppression_directive_on_a_mutable_default(tool_use, run_hook):
    # Arrange
    content = "# noqa: B006\ndef collect(items: list[str] = []) -> list[str]:\n    return items\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/collect.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "banned-prose-chars"
HOOK_SOURCE = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
EM_DASH = chr(0x2014)


def _load() -> ModuleType:
    if str(HOOK_SOURCE.parent) not in sys.path:
        sys.path.insert(0, str(HOOK_SOURCE.parent))
    spec = importlib.util.spec_from_file_location("banned_prose_chars", HOOK_SOURCE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {HOOK_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hook_disabled_by_profile_allows_banned_text(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": f"echo a{EM_DASH}b"})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK})

    # Assert
    assert_allowed(result)


def test_write_to_a_test_path_is_not_scanned(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/tests/fixtures.md", "content": f"a{EM_DASH}b\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_without_a_file_path_is_still_scanned(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"content": f"a{EM_DASH}b\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "em dash")


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Write", {"file_path": "/repo/a.md", "content": 7}),
        ("Edit", {"file_path": "/repo/a.md", "new_string": 7}),
        ("MultiEdit", {"file_path": "/repo/a.md", "edits": ["x", {"new_string": 7}]}),
        ("Bash", {"command": 7}),
        ("Read", {"file_path": "/repo/a.md"}),
    ],
)
def test_collect_texts_ignores_non_text_fields(tool, tool_input):
    # Arrange
    module = _load()

    # Act
    texts = module.collect_texts(tool, tool_input)

    # Assert
    assert texts == []

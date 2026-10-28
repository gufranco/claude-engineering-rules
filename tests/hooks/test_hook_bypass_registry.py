from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from _lib.bypass_writer import set_bypass  # noqa: E402

CALL = re.compile(r"is_bypassed\((?:\"([^\"]+)\"|([A-Z_]+))\)")


def _bypass_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    ids = []
    for literal, constant in CALL.findall(text):
        if literal:
            ids = [*ids, literal]
            continue
        value = re.search(rf"^{constant} = \"([^\"]+)\"", text, re.MULTILINE)
        ids = [*ids, value.group(1)] if value else ids
    return sorted(set(ids))


BYPASSABLE = sorted(
    (path, hook_id) for path in HOOKS_DIR.glob("*.py") for hook_id in _bypass_ids(path)
)


@pytest.mark.parametrize(
    ("path", "hook_id"), BYPASSABLE, ids=[p.name for p, _ in BYPASSABLE]
)
def test_a_hook_with_a_live_bypass_entry_does_nothing(
    run_hook, tool_use, tmp_path, path, hook_id
):
    # Arrange
    state = set_bypass(hook_id, ttl_seconds=600, state_path=tmp_path / "bypass.json")
    payload = tool_use("Bash", {"command": "git commit -m 'x' && rm -rf /"})

    # Act
    result = run_hook(path, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert (result.code, result.stdout) == (0, "")


ENV_SWITCH = re.compile(r"os\.environ\.get\(\"([A-Z0-9_]+_DISABLE)\"\) == \"1\"")
SWITCHED = sorted(
    (path, name)
    for path in HOOKS_DIR.glob("*.py")
    for name in sorted(set(ENV_SWITCH.findall(path.read_text(encoding="utf-8"))))
)


@pytest.mark.parametrize(
    ("path", "variable"), SWITCHED, ids=[f"{p.name}:{v}" for p, v in SWITCHED]
)
def test_a_hook_switched_off_by_its_variable_does_nothing(
    run_hook, tool_use, path, variable
):
    # Arrange
    payload = tool_use("Bash", {"command": "git commit -m 'x' && rm -rf /"})

    # Act
    result = run_hook(path, payload, env={variable: "1"})

    # Assert
    assert (result.code, result.stdout) == (0, "")

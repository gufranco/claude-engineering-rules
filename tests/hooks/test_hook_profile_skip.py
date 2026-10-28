from __future__ import annotations

import re
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"
CALL = re.compile(r"should_run\((?:\"([^\"]+)\"|([A-Z_]+))\)")


def _hook_id(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    match = CALL.search(text)
    if match is None:
        return None
    if match.group(1):
        return match.group(1)
    constant = re.search(rf"^{match.group(2)} = \"([^\"]+)\"", text, re.MULTILINE)
    return constant.group(1) if constant else None


GATED = sorted(
    (path, hook_id)
    for path in HOOKS_DIR.glob("*.py")
    if (hook_id := _hook_id(path)) is not None
)


@pytest.mark.parametrize(("path", "hook_id"), GATED, ids=[p.name for p, _ in GATED])
def test_a_hook_disabled_by_profile_does_nothing(run_hook, tool_use, path, hook_id):
    # Arrange
    payload = tool_use("Bash", {"command": "git commit -m 'x' && rm -rf /"})

    # Act
    result = run_hook(path, payload, env={"CLAUDE_DISABLED_HOOKS": hook_id})

    # Assert
    assert (result.code, result.stdout, result.stderr) == (0, "", "")

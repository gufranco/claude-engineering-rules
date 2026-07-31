"""The hook harness must not inherit machine state.

A live entry in `~/.claude/.bypass-state.json`, set during ordinary work with
`scripts/bypass.py set`, makes every hook short-circuit. Without isolation the
suite reports blocking tests as failures and permissive tests as passes, and
the cause is invisible in the output.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_conftest():
    spec = importlib.util.spec_from_file_location(
        "harness_conftest", REPO_ROOT / "tests" / "conftest.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_env_neutralizes_the_ambient_bypass_registry():
    conftest = _load_conftest()

    env = conftest._build_env()

    assert env["CLAUDE_BYPASS_STATE"] == os.devnull


def test_a_test_can_still_point_the_registry_at_its_own_file(tmp_path):
    conftest = _load_conftest()
    state = tmp_path / "bypass.json"

    env = conftest._build_env({"CLAUDE_BYPASS_STATE": str(state)})

    assert env["CLAUDE_BYPASS_STATE"] == str(state)


def test_the_neutralized_registry_reads_as_empty():
    import sys

    sys.path.insert(0, str(REPO_ROOT / "hooks"))
    from _lib.bypass import is_bypassed

    assert is_bypassed("check-then-act-blocker", state_path=Path(os.devnull)) is False


def test_a_blocking_hook_still_blocks_under_the_harness(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": (
                "const existing = await db.seat.findFirst({ where: { showId } });\n"
                "await db.seat.create({ data: { showId } });\n"
            ),
        },
    )

    assert_blocks(
        "check-then-act-blocker",
        payload,
        "read that decides a write",
        env={"CHECK_THEN_ACT_ENFORCE": "1"},
    )

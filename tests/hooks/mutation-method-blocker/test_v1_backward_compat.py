"""Backward-compatibility shim regression test.

Plan item 288. The v1 stderr emit is preserved indefinitely per D44.
This test guarantees that the hook produces v1 stderr output regardless
of whether `CLAUDE_HOOK_API_VERSION` is unset (legacy callers) or set to
`1` (explicit v1 callers). v2-aware callers still receive the JSON
envelope on stdout in addition to v1 stderr; the contract is dual-emit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOOK = ROOT / "hooks" / "mutation-method-blocker.py"


def _run(
    payload: dict, env_overrides: dict[str, str] | None = None
) -> tuple[int, str, str]:
    env = dict(os.environ)
    env.pop("CLAUDE_HOOK_API_VERSION", None)
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _block_payload() -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/tmp/v1compat.ts",
            "content": "const a = [];\na.push(1);\n",
        },
    }


def test_v1_stderr_emitted_when_api_version_unset() -> None:
    code, _stdout, stderr = _run(_block_payload(), env_overrides=None)
    assert code == 2
    assert "Blocked" in stderr or "mutation" in stderr.lower()


def test_v1_stderr_emitted_when_api_version_1() -> None:
    code, _stdout, stderr = _run(
        _block_payload(), env_overrides={"CLAUDE_HOOK_API_VERSION": "1"}
    )
    assert code == 2
    assert "Blocked" in stderr or "mutation" in stderr.lower()


def test_v2_envelope_emitted_alongside_v1() -> None:
    """v2 stdout envelope is dual-emitted; v1 stderr never disappears."""
    code, stdout, stderr = _run(_block_payload(), env_overrides=None)
    assert code == 2
    assert stderr.strip(), "v1 stderr must always be present"
    assert "{" in stdout, "v2 stdout envelope must always be present"
    body = json.loads(stdout)
    assert body["hookSpecificOutput"]["permissionDecision"] == "deny"
    reason = body["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason == stderr.split("\n", 1)[0] or reason in stderr


def test_v1_stderr_emitted_when_api_version_garbage() -> None:
    """An unrecognized version string must still produce v1 stderr."""
    code, _stdout, stderr = _run(
        _block_payload(), env_overrides={"CLAUDE_HOOK_API_VERSION": "garbage"}
    )
    assert code == 2
    assert stderr.strip()

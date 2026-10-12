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
    # Arrange
    payload = _block_payload()

    # Act
    code, _stdout, stderr = _run(payload, env_overrides=None)

    # Assert
    assert code == 2
    assert "Blocked" in stderr


def test_v1_stderr_emitted_when_api_version_1() -> None:
    # Arrange
    payload = _block_payload()

    # Act
    code, _stdout, stderr = _run(
        payload, env_overrides={"CLAUDE_HOOK_API_VERSION": "1"}
    )

    # Assert
    assert code == 2
    assert "Blocked" in stderr


def test_v2_envelope_emitted_alongside_v1() -> None:
    # Arrange
    payload = _block_payload()

    # Act
    code, stdout, stderr = _run(payload, env_overrides=None)

    # Assert
    assert code == 2
    assert stderr.strip() != "", "v1 stderr must always be present"
    assert "{" in stdout, "v2 stdout envelope must always be present"
    body = json.loads(stdout)
    assert body["hookSpecificOutput"]["permissionDecision"] == "deny"
    reason = body["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason in stderr


def test_v1_stderr_emitted_when_api_version_garbage() -> None:
    # Arrange
    payload = _block_payload()

    # Act
    code, _stdout, stderr = _run(
        payload, env_overrides={"CLAUDE_HOOK_API_VERSION": "garbage"}
    )

    # Assert
    assert code == 2
    assert stderr.strip() != ""

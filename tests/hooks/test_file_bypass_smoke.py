from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

import pytest
from _helpers.cov_env import apply_coverage_env

ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = ROOT / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from _lib.bypass_writer import set_bypass  # noqa: E402

PAYLOADS_FILE = Path(__file__).resolve().parent / "bypass_smoke_payloads.json"


class SmokeCase(TypedDict):
    env: dict[str, str]
    payload: dict[str, object]


BLOCKING_PAYLOADS: dict[str, SmokeCase] = json.loads(
    PAYLOADS_FILE.read_text(encoding="utf-8")
)
CREDENTIAL_VARS = ("GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN", "GLAB_TOKEN")
TIMEOUT_S = 30
BYPASS_TTL_S = 120


def _env(case: SmokeCase, state: Path) -> dict[str, str]:
    inherited = {k: v for k, v in os.environ.items() if k not in CREDENTIAL_VARS}
    return apply_coverage_env(
        {**inherited, **case["env"], "CLAUDE_BYPASS_STATE": str(state)}
    )


def _run(hook: str, case: SmokeCase, state: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / f"{hook}.py")],
        input=json.dumps(case["payload"]),
        capture_output=True,
        text=True,
        env=_env(case, state),
        timeout=TIMEOUT_S,
        check=False,
    )


@pytest.mark.parametrize("hook", sorted(BLOCKING_PAYLOADS))
def test_hook_blocks_the_payload_when_no_bypass_is_set(
    hook: str, tmp_path: Path
) -> None:
    # Arrange
    state = tmp_path / ".bypass-state.json"
    case = BLOCKING_PAYLOADS[hook]

    # Act
    result = _run(hook, case, state)

    # Assert
    assert result.returncode == 2, result.stderr[:400]


@pytest.mark.parametrize("hook", sorted(BLOCKING_PAYLOADS))
def test_file_bypass_allows_a_payload_the_hook_otherwise_blocks(
    hook: str, tmp_path: Path
) -> None:
    # Arrange
    state = tmp_path / ".bypass-state.json"
    set_bypass(hook, ttl_seconds=BYPASS_TTL_S, state_path=state)
    case = BLOCKING_PAYLOADS[hook]

    # Act
    result = _run(hook, case, state)

    # Assert
    assert result.returncode == 0, result.stderr[:400]
    assert "Blocked" not in result.stderr

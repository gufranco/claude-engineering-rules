from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env  # noqa: E402

from _ai_review_request_support import HOOK_PATH, payload

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.pr_session_ledger import opened  # noqa: E402

fake = Faker()
Faker.seed(3307)
NOW = 1_800_000_000.0


def _created(command: str, stdout: str, session: str, cwd: str = "/work") -> dict:
    return {**payload(command, stdout=stdout, cwd=cwd), "session_id": session}


def test_a_created_pr_is_recorded_for_the_session(hook, tmp_path):
    # Arrange
    session = fake.uuid4()
    data = _created(
        "gh pr create -t x -b y", "https://github.com/acme/app/pull/671\n", session
    )

    # Act
    hook.record_created(data, tmp_path, NOW)

    # Assert
    assert opened(session, "acme/app", tmp_path) == ("acme/app#671",)


@pytest.mark.parametrize("command", ["git push", "gh pr ready 9"])
def test_a_push_or_a_ready_call_records_nothing(hook, tmp_path, command):
    # Arrange
    data = _created(command, "https://github.com/acme/app/pull/9\n", fake.uuid4())

    # Act
    hook.record_created(data, tmp_path, NOW)

    # Assert
    assert list(tmp_path.iterdir()) == []


def test_the_hook_records_the_pr_end_to_end(fake_env, tmp_path):
    # Arrange
    session = fake.uuid4()
    ledger = tmp_path / "ledger"
    data = _created(
        "gh pr create -t x -b y",
        "https://github.com/acme/app/pull/7\n",
        session,
        cwd=str(fake_env["repo"]),
    )
    env = apply_coverage_env(
        {
            **os.environ,
            **fake_env["env"],
            "CLAUDE_BYPASS_STATE": "/dev/null",
            "CLAUDE_PR_LEDGER_DIR": str(ledger),
        }
    )

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(data),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    assert opened(session, "acme/app", ledger) == ("acme/app#7",)

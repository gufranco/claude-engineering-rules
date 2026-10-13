from __future__ import annotations

import json
import os
import subprocess
import sys


from _helpers.cov_env import apply_coverage_env  # noqa: E402

from _ai_review_request_support import HOOK_PATH, login, payload, run_cli


def test_push_end_to_end_labels_my_pr(fake_env):
    # Arrange
    stdin = json.dumps(payload("git push", cwd=str(fake_env["repo"])))
    env = apply_coverage_env(
        {**os.environ, **fake_env["env"], "CLAUDE_BYPASS_STATE": "/dev/null"}
    )

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # Assert
    assert json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"] == (
        "ai-review: acme/app#7 added label `claude-review`"
    )
    assert "repos/acme/app/issues/7/labels -X POST -f labels[]=claude-review" in (
        fake_env["log"].read_text()
    )


def test_cli_dry_run_prints_without_writing(fake_env):
    # Arrange
    env = apply_coverage_env({**os.environ, **fake_env["env"]})
    me = fake_env["me"]

    # Act
    proc = run_cli(env, "--repo", "acme/app", "--pr", "7", "--account", me, "--dry-run")

    # Assert
    assert (proc.returncode, proc.stdout.strip()) == (
        0,
        "ai-review: acme/app#7 would add label `claude-review`",
    )
    assert "POST" not in fake_env["log"].read_text()


def test_cli_reports_a_pr_that_is_not_mine(fake_env):
    # Arrange
    env = apply_coverage_env({**os.environ, **fake_env["env"]})
    stranger = login()

    # Act
    proc = run_cli(env, "--repo", "acme/app", "--pr", "7", "--account", stranger)

    # Assert
    assert proc.stdout.strip() == (
        f"ai-review: acme/app#7 is not an open PR authored by {stranger}"
    )


def test_hook_reports_a_failure_without_blocking(fake_env, tmp_path):
    # Arrange
    broken = tmp_path / "bin" / "gh"
    broken.write_text("#!/bin/sh\necho 'HTTP 502' >&2\nexit 1\n")
    stdin = json.dumps(payload("git push", cwd=str(fake_env["repo"])))
    env = apply_coverage_env(
        {**os.environ, **fake_env["env"], "CLAUDE_BYPASS_STATE": "/dev/null"}
    )

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    assert context.startswith("ai-review: failed:") is True

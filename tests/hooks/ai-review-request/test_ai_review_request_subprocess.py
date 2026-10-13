from __future__ import annotations

import json
import subprocess


from _helpers.raising import raising  # noqa: E402

from _ai_review_request_support import (
    Deps,
    _pr_lookup_failing_for,
    login,
    payload,
    run_subprocess,
)


def test_disabled_hook_exits_quietly():
    # Arrange
    stdin = json.dumps(payload("git push"))

    # Act
    proc = run_subprocess(stdin, {"AI_REVIEW_REQUEST_DISABLE": "1"})

    # Assert
    assert (proc.returncode, proc.stdout) == (0, "")


def test_malformed_stdin_exits_quietly():
    # Arrange
    stdin = "not json"

    # Act
    proc = run_subprocess(stdin, {})

    # Assert
    assert (proc.returncode, proc.stdout) == (0, "")


def test_unrelated_command_exits_quietly_end_to_end():
    # Arrange
    stdin = json.dumps(payload("ls -la"))

    # Act
    proc = run_subprocess(stdin, {})

    # Assert
    assert (proc.returncode, proc.stdout) == (0, "")


def test_summaries_are_emitted_as_additional_context(hook, capsys):
    # Arrange
    items = ["ai-review: acme/app#1 ok"]

    # Act
    hook.emit(items)

    # Assert
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "ai-review: acme/app#1 ok",
        }
    }


def test_a_directory_that_is_not_a_repository_is_ignored(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[me])
    deps.git = raising(subprocess.CalledProcessError(128, ["git"]))

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert summaries == []


def test_an_account_without_access_is_skipped_when_finding_the_pr(hook):
    # Arrange
    me = login()
    blind = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[blind, me])
    deps.branch_pr_number = _pr_lookup_failing_for(
        deps.branch_pr_number, f"token-{blind}", hook.ai_review.GhError("HTTP 404")
    )

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == (
        ["ai-review: acme/app#7 ok"],
        [("acme/app#7", me)],
    )


def test_ready_with_a_number_outside_a_repository_does_nothing(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me)
    deps.git = lambda args, cwd: "https://gitlab.com/acme/app\n"

    # Act
    summaries = hook.handle(
        payload(f"GH_TOKEN=$(gh auth token --user {me}) gh pr ready 3"),
        deps.bundle(),
    )

    # Assert
    assert summaries == []


def test_minimal_profile_skips_the_hook():
    # Arrange
    stdin = json.dumps(payload("git push"))

    # Act
    proc = run_subprocess(stdin, {"CLAUDE_HOOK_PROFILE": "minimal"})

    # Assert
    assert (proc.returncode, proc.stdout) == (0, "")


def test_ssh_host_resolution_reads_ssh_config(hook, monkeypatch, tmp_path):
    # Arrange
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ssh = bin_dir / "ssh"
    ssh.write_text("#!/bin/sh\necho 'user git'\necho 'hostname github.com'\n")
    ssh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")

    # Act
    resolved = hook.ssh_hostname("github-work")

    # Assert
    assert resolved == "github.com"


def test_ssh_host_resolution_falls_back_to_the_alias(hook, monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("PATH", str(tmp_path))

    # Act
    resolved = hook.ssh_hostname("github-work")

    # Assert
    assert resolved == "github-work"

from __future__ import annotations

import importlib.util
import json
import os
import random
import string
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parents[2]
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _helpers.raising import raising  # noqa: E402

HOOK = "ai-review-request"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
RNG = random.Random(20261004)


def login() -> str:
    return "".join(RNG.choices(string.ascii_lowercase, k=10))


def load_hook():
    spec = importlib.util.spec_from_file_location("ai_review_request", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ai_review_request"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook():
    return load_hook()


class Deps:
    def __init__(self, hook, *, owner_of_pr: str, accounts=(), branch_pr=7):
        self.hook = hook
        self.owner_of_pr = owner_of_pr
        self.accounts = list(accounts)
        self.branch_pr = branch_pr
        self.requests: list[tuple[str, str]] = []

    def request(self, target, *, account, token):
        self.requests = [*self.requests, (f"{target.slug}#{target.number}", account)]
        if account != self.owner_of_pr:
            return ""
        return f"ai-review: {target.slug}#{target.number} ok"

    def token(self, account):
        return f"token-{account}"

    def list_accounts(self):
        return self.accounts

    def git(self, args, cwd):
        if args[:2] == ["remote", "get-url"]:
            return "git@github.com:acme/app.git\n"
        return "feature/x\n"

    def branch_pr_number(self, owner, name, branch, token):
        return self.branch_pr

    def resolve_host(self, host):
        return {"github-work": "github.com"}.get(host, host)

    def bundle(self):
        return self.hook.Dependencies(
            request=self.request,
            token=self.token,
            list_accounts=self.list_accounts,
            git=self.git,
            branch_pr_number=self.branch_pr_number,
            resolve_host=self.resolve_host,
        )


def payload(command: str, stdout: str = "", cwd: str = "/work") -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout, "stderr": ""},
        "cwd": cwd,
    }


def _recording(original, seen: list[str]):
    def git(args, cwd):
        seen.append(cwd)
        return original(args, cwd)

    return git


def _request_failing_for(original, bad: str, error: Exception):
    def request(target, *, account, token):
        if account == bad:
            raise error
        return original(target, account=account, token=token)

    return request


def _pr_lookup_failing_for(original, token_to_fail: str, error: Exception):
    def branch_pr_number(owner, name, branch, token):
        if token == token_to_fail:
            raise error
        return original(owner, name, branch, token)

    return branch_pr_number


def _git_with_remote(remote_url: str):
    def git(args, cwd):
        return {"remote": remote_url}.get(args[0], "feature/x\n")

    return git


def test_pr_create_uses_the_url_and_the_named_account(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me)
    command = f"GH_TOKEN=$(gh auth token --user {me}) gh pr create --fill"

    # Act
    summaries = hook.handle(
        payload(command, "https://github.com/acme/app/pull/4290\n"), deps.bundle()
    )

    # Assert
    assert (summaries, deps.requests) == (
        ["ai-review: acme/app#4290 ok"],
        [("acme/app#4290", me)],
    )


def test_pr_create_without_a_url_does_nothing(hook):
    # Arrange
    deps = Deps(hook, owner_of_pr=login())

    # Act
    summaries = hook.handle(payload("gh pr create --fill", "error"), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == ([], [])


def test_pr_ready_with_a_number(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me)

    # Act
    summaries = hook.handle(
        payload(f"GH_TOKEN=$(gh auth token --user {me}) gh pr ready 31"),
        deps.bundle(),
    )

    # Assert
    assert deps.requests == [("acme/app#31", me)]
    assert summaries == ["ai-review: acme/app#31 ok"]


def test_pr_ready_with_a_url(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me)
    command = (
        f"GH_TOKEN=$(gh auth token --user {me}) gh pr ready "
        "https://github.com/other/repo/pull/9"
    )

    # Act
    hook.handle(payload(command), deps.bundle())

    # Assert
    assert deps.requests == [("other/repo#9", me)]


def test_pr_ready_without_an_argument_uses_the_branch(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, branch_pr=55)

    # Act
    hook.handle(
        payload(f"GH_TOKEN=$(gh auth token --user {me}) gh pr ready"), deps.bundle()
    )

    # Assert
    assert deps.requests == [("acme/app#55", me)]


def test_push_tries_accounts_until_the_author_matches(hook):
    # Arrange
    me = login()
    other = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[other, me])

    # Act
    summaries = hook.handle(payload("git push -u origin feature/x"), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == (
        ["ai-review: acme/app#7 ok"],
        [("acme/app#7", other), ("acme/app#7", me)],
    )


def test_push_with_no_open_pr_does_nothing(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[me], branch_pr=None)

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == ([], [])


def test_push_to_someone_elses_pr_reports_nothing(hook):
    # Arrange
    deps = Deps(hook, owner_of_pr=login(), accounts=[login(), login()])

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert summaries == []


def test_git_dash_c_and_cd_change_the_directory(hook):
    # Arrange
    me = login()
    seen: list[str] = []
    deps = Deps(hook, owner_of_pr=me, accounts=[me])
    deps.git = _recording(deps.git, seen)

    # Act
    hook.handle(payload("cd sub && git -C inner push"), deps.bundle())

    # Assert
    assert set(seen) == {"/work/sub/inner"}


def test_non_github_remote_is_ignored(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[me])
    deps.git = lambda args, cwd: "https://gitlab.com/acme/app.git\n"

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == ([], [])


def test_a_failing_account_is_skipped(hook):
    # Arrange
    me = login()
    bad = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[bad, me])
    deps.request = _request_failing_for(
        deps.request, bad, hook.ai_review.GhError("HTTP 404")
    )

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert summaries == ["ai-review: acme/app#7 ok"]


def test_every_account_failing_is_reported(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[me])
    deps.request = raising(hook.ai_review.GhError("HTTP 502"))

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert summaries == ["ai-review: acme/app#7 failed: HTTP 502"]


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "echo 'gh pr create'",
        "git pull",
        "gh pr view 3",
        "cat <<'EOF'\ngit push\nEOF",
    ],
)
def test_unrelated_commands_do_nothing(hook, command):
    # Arrange
    deps = Deps(hook, owner_of_pr=login(), accounts=[login()])

    # Act
    summaries = hook.handle(payload(command), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == ([], [])


def test_non_bash_tool_does_nothing(hook):
    # Arrange
    deps = Deps(hook, owner_of_pr=login())

    # Act
    summaries = hook.handle({"tool_name": "Write", "tool_input": {}}, deps.bundle())

    # Assert
    assert summaries == []


def test_accounts_are_capped(hook):
    # Arrange
    me = login()
    many = [login() for _ in range(hook.MAX_ACCOUNTS + 3)] + [me]
    deps = Deps(hook, owner_of_pr=me, accounts=many)

    # Act
    hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert len(deps.requests) == hook.MAX_ACCOUNTS


def run_subprocess(
    stdin: str, env_extra: dict[str, str]
) -> subprocess.CompletedProcess:
    import os

    env = apply_coverage_env(
        {**os.environ, "CLAUDE_BYPASS_STATE": os.devnull, **env_extra}
    )
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
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


FAKE_GH = r"""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(" ".join(args) + "\n")
joined = " ".join(args)
me = os.environ["FAKE_GH_ME"]
if args[:2] == ["auth", "status"]:
    print(json.dumps({"hosts": {"github.com": [{"login": me}]}}))
elif args[:2] == ["auth", "token"]:
    print("tok-" + args[-1])
elif "/pulls" in joined and "--jq" in args:
    print("7")
elif "pullRequest(number" in joined:
    print(json.dumps({"data": {"repository": {"pullRequest": {
        "state": "OPEN", "author": {"login": me},
        "labels": {"nodes": []}, "comments": {"nodes": []},
        "reviews": {"nodes": []}}}}}))
elif "pullRequests(last" in joined:
    print(json.dumps({"data": {"repository": {
        "label": {"name": "claude-review"}, "pullRequests": {"nodes": []}}}}))
else:
    print("{}")
"""


@pytest.fixture
def fake_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    me = login()
    repo = tmp_path / "repo"
    repo.mkdir()
    git_env = {**os.environ, "HOME": str(tmp_path)}
    for cmd in (
        ["git", "init", "-q", "-b", "feature"],
        ["git", "remote", "add", "origin", "git@github.com:acme/app.git"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, env=git_env)
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "FAKE_GH_LOG": str(tmp_path / "gh.log"),
        "FAKE_GH_ME": me,
    }
    return {"env": env, "repo": repo, "log": tmp_path / "gh.log", "me": me}


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
    proc = subprocess.run(
        [
            sys.executable,
            str(HOOK_PATH),
            "--repo",
            "acme/app",
            "--pr",
            "7",
            "--account",
            me,
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

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
    proc = subprocess.run(
        [
            sys.executable,
            str(HOOK_PATH),
            "--repo",
            "acme/app",
            "--pr",
            "7",
            "--account",
            stranger,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

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


def test_minimal_profile_skips_the_hook():
    # Arrange
    stdin = json.dumps(payload("git push"))

    # Act
    proc = run_subprocess(stdin, {"CLAUDE_HOOK_PROFILE": "minimal"})

    # Assert
    assert (proc.returncode, proc.stdout) == (0, "")


def test_push_through_an_ssh_alias_reaches_github(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[me])
    deps.git = _git_with_remote("git@github-work:acme/app.git\n")

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert summaries == ["ai-review: acme/app#7 ok"]


@pytest.mark.parametrize(
    "flag", ["--repo other/thing", "-R other/thing", "--repo=other/thing"]
)
def test_ready_honors_an_explicit_repository(hook, flag):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me)
    command = f"GH_TOKEN=$(gh auth token --user {me}) gh pr ready 12 {flag}"

    # Act
    hook.handle(payload(command), deps.bundle())

    # Assert
    assert deps.requests == [("other/thing#12", me)]


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

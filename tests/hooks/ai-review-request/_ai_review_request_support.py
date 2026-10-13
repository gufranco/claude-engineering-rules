from __future__ import annotations

import importlib.util
import random
import string
import subprocess
import sys
from pathlib import Path


from _helpers.cov_env import apply_coverage_env  # noqa: E402


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


def run_cli(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK_PATH), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

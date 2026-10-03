#!/usr/bin/env python3
"""Request AI reviews after a command opens, readies, or pushes to my PR.

PostToolUse on Bash. Fires after `gh pr create`, `gh pr ready` and
`git push`, finds the pull request, and asks `_lib/ai_review.py` to request
every review the repository supports. Only an open pull request authored by
the acting account is touched. The hook never blocks: it always exits 0 and
reports one line per pull request as additional context.

Account: the `--user <login>` the command named, otherwise every logged-in
account in turn until one is the pull request's author, at most four.

CLI, for a manual or dry run:
    python3 hooks/ai-review-request.py --repo owner/name --pr 42 \
        [--account login] [--dry-run]

Bypass: AI_REVIEW_REQUEST_DISABLE=1, or the bypass registry.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib import ai_review  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.shell_segments import command_head, quoted_segments  # noqa: E402

try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


HOOK_ID = "ai-review-request"
MAX_ACCOUNTS = 4
SUBPROCESS_TIMEOUT_SECONDS = 20
NAMED_ACCOUNT = re.compile(r"--user\s+([A-Za-z0-9][A-Za-z0-9-]*)")


class TriggerKind(str, Enum):
    CREATE = "create"
    READY = "ready"
    PUSH = "push"


GH_PR_ACTIONS = (TriggerKind.CREATE.value, TriggerKind.READY.value)
REPO_FLAGS = ("--repo", "-R")


@dataclass(frozen=True)
class Dependencies:
    request: Callable[..., str]
    token: Callable[[str], str]
    list_accounts: Callable[[], list[str]]
    git: Callable[[list[str], str], str]
    branch_pr_number: Callable[[str, str, str, str], "int | None"]
    resolve_host: Callable[[str], str]


@dataclass(frozen=True)
class Trigger:
    kind: TriggerKind
    argument: str
    cwd: str
    repo: str = ""


def _gh_pr_action(tokens: list[str]) -> tuple[str, list[str]] | None:
    for i in range(len(tokens) - 2):
        head = os.path.basename(tokens[i])
        if head == "gh" and tokens[i + 1] == "pr" and tokens[i + 2] in GH_PR_ACTIONS:
            return tokens[i + 2], tokens[i + 3 :]
    return None


def _git_push_dir(args: list[str], cwd: str) -> str | None:
    directory, i = cwd, 1
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            directory = os.path.join(directory, os.path.expanduser(args[i + 1]))
        i += 2 if args[i] in ("-C", "-c") else 1
    return directory if i < len(args) and args[i] == "push" else None


def _split_pr_args(args: list[str]) -> tuple[list[str], str]:
    """Positional arguments, and the `--repo`/`-R` value when one is given."""
    positional: list[str] = []
    repo = ""
    skip = False
    for index, arg in enumerate(args):
        if skip:
            skip = False
            continue
        if arg in REPO_FLAGS:
            repo, skip = (args[index + 1] if index + 1 < len(args) else ""), True
        elif arg.startswith("--repo="):
            repo = arg.split("=", 1)[1]
        elif not arg.startswith("-"):
            positional = [*positional, arg]
    return positional, repo


def find_triggers(command: str, cwd: str) -> list[Trigger]:
    """Every PR-moving command in `command`, with the directory it runs in."""
    triggers: list[Trigger] = []
    current = cwd
    for tokens in quoted_segments(command):
        head, args = command_head(tokens)
        if head == "cd" and len(args) > 1:
            current = os.path.join(current, os.path.expanduser(args[1]))
            continue
        action = _gh_pr_action(tokens)
        if action:
            positional, repo = _split_pr_args(action[1])
            first = positional[0] if positional else ""
            triggers = [
                *triggers,
                Trigger(TriggerKind(action[0]), first, current, repo),
            ]
            continue
        push_dir = _git_push_dir(args, current) if head == "git" else None
        if push_dir:
            triggers = [*triggers, Trigger(TriggerKind.PUSH, "", push_dir)]
    return triggers


def _candidates(command: str, deps: Dependencies) -> list[str]:
    named = list(dict.fromkeys(NAMED_ACCOUNT.findall(command)))
    return (named or deps.list_accounts())[:MAX_ACCOUNTS]


def _remote(deps: Dependencies, cwd: str) -> tuple[str, str] | None:
    try:
        url = deps.git(["remote", "get-url", "origin"], cwd)
        return ai_review.parse_remote(url, deps.resolve_host)
    except (OSError, subprocess.SubprocessError):
        return None


def _request_as(
    target: ai_review.Target, accounts: list[str], deps: Dependencies
) -> str:
    error = ""
    for account in accounts:
        try:
            summary = deps.request(target, account=account, token=deps.token(account))
        except ai_review.GhError as exc:
            error = str(exc)
            continue
        if summary:
            return summary
    return f"ai-review: {target.slug}#{target.number} failed: {error}" if error else ""


def _branch_number(
    remote: tuple[str, str], branch: str, account: str, deps: Dependencies
) -> int | None:
    try:
        return deps.branch_pr_number(remote[0], remote[1], branch, deps.token(account))
    except ai_review.GhError:
        return None


def _branch_request(trigger: Trigger, accounts: list[str], deps: Dependencies) -> str:
    remote = _remote(deps, trigger.cwd)
    if remote is None:
        return ""
    branch = deps.git(["branch", "--show-current"], trigger.cwd).strip()
    for index, account in enumerate(accounts):
        number = _branch_number(remote, branch, account, deps)
        if number is not None:
            target = ai_review.Target(remote[0], remote[1], number)
            return _request_as(target, accounts[index:], deps)
    return ""


def _ready_targets(
    trigger: Trigger, deps: Dependencies
) -> tuple[ai_review.Target, ...]:
    if not trigger.argument.isdigit():
        return ai_review.pr_urls(trigger.argument)
    owner, _, name = trigger.repo.partition("/")
    remote = (owner, name) if owner and name else _remote(deps, trigger.cwd)
    return (
        (ai_review.Target(remote[0], remote[1], int(trigger.argument)),)
        if remote
        else ()
    )


def _summaries_for(
    trigger: Trigger, stdout: str, accounts: list[str], deps: Dependencies
) -> list[str]:
    if trigger.kind is TriggerKind.CREATE:
        targets = ai_review.pr_urls(stdout)
    elif trigger.kind is TriggerKind.READY and trigger.argument:
        targets = _ready_targets(trigger, deps)
    else:
        return [s for s in [_branch_request(trigger, accounts, deps)] if s]
    return [s for s in (_request_as(t, accounts, deps) for t in targets) if s]


def handle(data: dict, deps: Dependencies) -> list[str]:
    """One summary line per pull request a review was requested on."""
    if data.get("tool_name") != "Bash":
        return []
    command = (data.get("tool_input") or {}).get("command") or ""
    triggers = find_triggers(command, data.get("cwd") or os.getcwd())
    if not triggers:
        return []
    response = data.get("tool_response")
    stdout = response.get("stdout", "") if isinstance(response, dict) else ""
    accounts = _candidates(command, deps)
    summaries = [s for t in triggers for s in _summaries_for(t, stdout, accounts, deps)]
    return list(dict.fromkeys(summaries))


def _run(args: list[str], cwd: str | None = None) -> str:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=True,
    ).stdout


def gh_token(account: str) -> str:
    return _run(["gh", "auth", "token", "--user", account]).strip()


def gh_accounts() -> list[str]:
    hosts = json.loads(_run(["gh", "auth", "status", "--json", "hosts"]))["hosts"]
    return [entry["login"] for entry in hosts.get("github.com", [])]


def git_output(args: list[str], cwd: str) -> str:
    return _run(["git", *args], cwd=cwd)


def branch_pr_number(owner: str, name: str, branch: str, token: str) -> int | None:
    query = ["-f", f"head={owner}:{branch}", "-f", "state=open"]
    args = [
        "api",
        f"repos/{owner}/{name}/pulls",
        "-X",
        "GET",
        *query,
        "--jq",
        ".[0].number // empty",
    ]
    out = ai_review.run_gh(args, token).strip()
    return int(out) if out.isdigit() else None


def ssh_hostname(host: str) -> str:
    """The real host behind an SSH alias, per `ssh -G`; the alias when unknown."""
    try:
        config = _run(["ssh", "-G", host])
    except (OSError, subprocess.SubprocessError):
        return host
    names = [
        line.split()[1] for line in config.splitlines() if line.startswith("hostname ")
    ]
    return names[0] if names else host


def request_now(target: ai_review.Target, *, account: str, token: str) -> str:
    return ai_review.request_reviews(
        target, account=account, token=token, now=time.time()
    )


def default_dependencies() -> Dependencies:
    return Dependencies(
        request=request_now,
        token=gh_token,
        list_accounts=gh_accounts,
        git=git_output,
        branch_pr_number=branch_pr_number,
        resolve_host=ssh_hostname,
    )


def emit(summaries: list[str]) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(summaries),
        }
    }
    sys.stdout.write(json.dumps(payload))


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Request AI reviews on one pull request."
    )
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--account", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    owner, _, name = args.repo.partition("/")
    target = ai_review.Target(owner, name, args.pr)
    summary = ai_review.request_reviews(
        target,
        account=args.account,
        token=gh_token(args.account),
        now=time.time(),
        dry_run=args.dry_run,
    )
    print(
        summary
        or f"ai-review: {args.repo}#{args.pr} is not an open PR authored by {args.account}"
    )
    return 0


def main() -> int:
    if sys.argv[1:]:
        return cli(sys.argv[1:])
    if os.environ.get("AI_REVIEW_REQUEST_DISABLE") == "1" or is_bypassed(HOOK_ID):
        return 0
    if not should_run(HOOK_ID):
        return 0
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    try:
        summaries = handle(data, default_dependencies())
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
        ai_review.GhError,
    ) as exc:
        _audit(hook=HOOK_ID, decision="error", tool="Bash", reason=str(exc)[:200])
        summaries = [f"ai-review: failed: {exc}"]
    if summaries:
        emit(summaries)
    return 0


if __name__ == "__main__":
    sys.exit(main())

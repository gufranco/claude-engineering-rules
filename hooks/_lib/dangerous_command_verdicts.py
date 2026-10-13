from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Sequence
from typing import NoReturn

from _lib.audit_log import record as audit
from _lib.dangerous_command_push import (
    current_branch,
    names_protected_ref,
    push_cwd as resolve_push_cwd,
)
from _lib.hook_warning import emit_warning

HOOK_NAME = "dangerous-command-blocker"
PROTECTED_BRANCHES = ("main", "master", "develop")
PUSH_BYPASS_ENV = "ALLOW_PROTECTED_BRANCH_PUSH"
AUDIT_COMMAND_LIMIT = 300

Patterns = Sequence[tuple[str, str]]
SoloRoot = Callable[[str | None, str], str]


def allow(notices: list[str]) -> NoReturn:
    if notices:
        emit_warning("\n\n".join(notices))
    sys.exit(0)


def refuse_unreadable(problem: str) -> NoReturn:
    audit(
        hook=HOOK_NAME,
        decision="block",
        level="unreadable-input",
        reason=problem,
    )
    print(
        f"BLOCKED: dangerous-command-blocker could not read its input: {problem}.\n"
        "The command was not checked, so it does not run. The harness sends a "
        'JSON object such as {"tool_name": "Bash", "tool_input": {"command": "..."}}.',
        file=sys.stderr,
    )
    sys.exit(2)


def block_catastrophic(command: str, matched: str, patterns: Patterns) -> None:
    for pattern, label in patterns:
        if not re.search(pattern, matched):
            continue
        audit(
            hook=HOOK_NAME,
            decision="block",
            level="catastrophic",
            reason=f"catastrophic: {label}",
            pattern=pattern,
            command=command[:AUDIT_COMMAND_LIMIT],
        )
        print(
            f"BLOCKED: Catastrophic command detected: {label}.\nCommand: {command}",
            file=sys.stderr,
        )
        sys.exit(2)


def block_critical(command: str, matched: str, patterns: Patterns) -> None:
    for pattern, reason in patterns:
        if not re.search(pattern, matched):
            continue
        audit(
            hook=HOOK_NAME,
            decision="block",
            level="critical",
            pattern=pattern,
            reason=reason,
            command=command[:AUDIT_COMMAND_LIMIT],
        )
        print(f"BLOCKED: {reason}\nCommand: {command}", file=sys.stderr)
        sys.exit(2)


def first_notice(
    command: str, matched: str, patterns: Patterns, prefix: str, suffix: str = ""
) -> list[str]:
    return [
        f"{prefix}{reason}\nCommand: {command}{suffix}"
        for pattern, reason in patterns
        if re.search(pattern, matched)
    ][:1]


def targets_protected(matched: str, branch: str) -> bool:
    names_ref = bool(re.search(r"\borigin\s+", matched)) and names_protected_ref(
        matched.split("origin", 1)[-1]
    )
    on_protected = branch in PROTECTED_BRANCHES and not re.search(
        r"\borigin\s+\w", matched
    )
    return names_ref or on_protected


def _allow_solo_push(
    command: str, branch: str, repo_root: str, notices: list[str]
) -> NoReturn:
    audit(
        hook=HOOK_NAME,
        decision="allow",
        level="protected-branch",
        reason=f"solo repo allowlisted ({repo_root})",
        branch=branch,
        command=command[:AUDIT_COMMAND_LIMIT],
    )
    allow(notices)


def _record_push_bypass(command: str, branch: str) -> None:
    audit(
        hook=HOOK_NAME,
        decision="bypass",
        level="protected-branch",
        reason=f"protected branch push ({branch or 'main'})",
        bypass_env=PUSH_BYPASS_ENV,
        branch=branch,
        command=command[:AUDIT_COMMAND_LIMIT],
    )


def _block_protected_push(command: str, branch: str) -> NoReturn:
    audit(
        hook=HOOK_NAME,
        decision="block",
        level="protected-branch",
        reason=f"protected branch push ({branch or 'main'})",
        branch=branch,
        command=command[:AUDIT_COMMAND_LIMIT],
    )
    print(
        f"BLOCKED: Direct push to protected branch ({branch or 'main/develop'}).\n"
        "Use a feature branch and create a PR instead.\n"
        "Solo repo with no PR workflow? Add it to ~/.claude/solo-repos.txt "
        "once instead of bypassing on every push.\n"
        "Bypass (one-off): export ALLOW_PROTECTED_BRANCH_PUSH=1 in the parent shell.\n"
        f"Command: {command}",
        file=sys.stderr,
    )
    sys.exit(2)


def check_protected_push(
    command: str, matched: str, notices: list[str], solo_root: SoloRoot
) -> None:
    push_cwd = resolve_push_cwd(command)
    command_cwd = push_cwd or ""
    branch = current_branch(command_cwd)
    if not targets_protected(matched, branch):
        return
    repo_root = solo_root(push_cwd, command_cwd)
    if repo_root:
        _allow_solo_push(command, branch, repo_root, notices)
    if os.environ.get(PUSH_BYPASS_ENV) != "1":
        _block_protected_push(command, branch)
    _record_push_bypass(command, branch)

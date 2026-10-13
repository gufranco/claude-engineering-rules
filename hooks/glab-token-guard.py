#!/usr/bin/env python3
"""Block glab CLI commands that don't have GITLAB_TOKEN set inline.

Prevents accidental use of the wrong GitLab account when multiple
instances or accounts are configured. The global config can change
at any time from another terminal, so every glab command must
explicitly set GITLAB_TOKEN and GITLAB_HOST.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


from _lib.cli_invocations import asks_for_help, Invocation, invocations  # noqa: E402

EXEMPT_SUBCOMMANDS = frozenset(
    {"auth", "config", "version", "--version", "help", "--help", "-h"}
)


def _logs_in(call: Invocation) -> bool:
    return call.args[:2] == ("auth", "login")


def _needs_token(call: Invocation) -> bool:
    if call.args[:1] and call.args[0] in EXEMPT_SUBCOMMANDS:
        return False
    if asks_for_help(call.args):
        return False
    return "GITLAB_TOKEN" not in call.assigned


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def main():
    if os.environ.get("GLAB_TOKEN_GUARD_DISABLE") == "1":
        return 0
    if is_bypassed("glab-token-guard"):
        return 0
    if not should_run("glab-token-guard"):
        sys.exit(0)
    data = read_hook_payload("glab-token-guard")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    calls = invocations(command, "glab")
    if any(_logs_in(call) for call in calls):
        print(
            "BLOCKED: glab auth login changes the global config "
            "and affects all terminals.\n"
            "Use GITLAB_TOKEN=<token> GITLAB_HOST=<host> glab <command> instead.\n"
            "Check the git remote to determine the correct instance.\n"
            "See: standards/multi-account-cli.md",
            file=sys.stderr,
        )
        _audit(
            hook="glab-token-guard",
            decision="block",
            tool="Bash",
            reason="glab CLI without explicit GITLAB_TOKEN",
            command_excerpt=command[:240],
        )
        sys.exit(2)

    if not any(_needs_token(call) for call in calls):
        sys.exit(0)

    print(
        "BLOCKED: glab command without explicit GITLAB_TOKEN.\n"
        "Multiple GitLab instances may be configured. The global config "
        "can change from another terminal at any time.\n"
        "Prefix with: GITLAB_TOKEN=<token> GITLAB_HOST=<host> glab ...\n"
        "Or export them: export GITLAB_TOKEN=<token> GITLAB_HOST=<host>\n"
        "Check git remote get-url origin to determine the correct instance.\n"
        "See: standards/multi-account-cli.md\n"
        f"Command: {command}",
        file=sys.stderr,
    )
    _audit(
        hook="glab-token-guard",
        decision="block",
        tool="Bash",
        reason="glab CLI without explicit GITLAB_TOKEN",
        command_excerpt=command[:240],
    )
    sys.exit(2)


if __name__ == "__main__":
    main()

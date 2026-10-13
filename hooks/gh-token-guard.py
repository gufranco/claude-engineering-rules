#!/usr/bin/env python3
"""Block gh CLI commands that don't have GH_TOKEN set inline.

Prevents accidental use of the wrong GitHub account when multiple
accounts are configured. The global active account can change at
any time from another terminal, so every gh command must explicitly
set GH_TOKEN.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


GH_AUTH_SWITCH = re.compile(r"\bgh\s+auth\s+switch\b")


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.cli_invocations import asks_for_help, Invocation, invocations  # noqa: E402
from _lib.shell_segments import mask_literal_text  # noqa: E402

EXEMPT_SUBCOMMANDS = frozenset(
    {
        "auth",
        "--version",
        "--help",
        "-h",
        "version",
        "help",
        "completion",
        "config",
        "alias",
    }
)


def _needs_token(call: Invocation) -> bool:
    if call.args[:1] and call.args[0] in EXEMPT_SUBCOMMANDS:
        return False
    if asks_for_help(call.args):
        return False
    if call.args[:2] == ("extension", "list"):
        return False
    return "GH_TOKEN" not in call.assigned


def main():
    if os.environ.get("GH_TOKEN_GUARD_DISABLE") == "1":
        return 0
    if is_bypassed("gh-token-guard"):
        return 0
    if not should_run("gh-token-guard"):
        sys.exit(0)
    data = read_hook_payload("gh-token-guard")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    scan = mask_literal_text(command)

    if GH_AUTH_SWITCH.search(scan):
        print(
            "BLOCKED: gh auth switch changes the global active account "
            "and affects all terminals.\n"
            "Use GH_TOKEN=$(gh auth token --user <account>) gh <command> instead.\n"
            "Check the git remote to determine the correct account.\n"
            "See: standards/multi-account-cli.md",
            file=sys.stderr,
        )
        _audit(
            hook="gh-token-guard",
            decision="block",
            tool="Bash",
            reason="gh CLI without explicit GH_TOKEN",
            command_excerpt=command[:240],
        )
        sys.exit(2)

    if not any(_needs_token(call) for call in invocations(command, "gh")):
        sys.exit(0)

    print(
        "BLOCKED: gh command without explicit GH_TOKEN.\n"
        "Multiple GitHub accounts are configured. The global active account "
        "can change from another terminal at any time.\n"
        "Prefix with: GH_TOKEN=$(gh auth token --user <account>) gh ...\n"
        "Or export it: export GH_TOKEN=$(gh auth token --user <account>)\n"
        "Check git remote get-url origin to determine the correct account.\n"
        "See: standards/multi-account-cli.md\n"
        f"Command: {command}",
        file=sys.stderr,
    )
    _audit(
        hook="gh-token-guard",
        decision="block",
        tool="Bash",
        reason="gh CLI without explicit GH_TOKEN",
        command_excerpt=command[:240],
    )
    sys.exit(2)


if __name__ == "__main__":
    main()

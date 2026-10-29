#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


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


AUTH_SWITCH_MESSAGE = (
    "BLOCKED: gh auth switch changes the global active account "
    "and affects all terminals.\n"
    "Use GH_TOKEN=$(gh auth token --user <account>) gh <command> instead.\n"
    "Check the git remote to determine the correct account.\n"
    "See: standards/multi-account-cli.md"
)

MISSING_TOKEN_MESSAGE = (
    "BLOCKED: gh command without explicit GH_TOKEN.\n"
    "Multiple GitHub accounts are configured. The global active account "
    "can change from another terminal at any time.\n"
    "Prefix with: GH_TOKEN=$(gh auth token --user <account>) gh ...\n"
    "Or export it: export GH_TOKEN=$(gh auth token --user <account>)\n"
    "Check git remote get-url origin to determine the correct account.\n"
    "See: standards/multi-account-cli.md\n"
)


def _block(message: str, command: str) -> int:
    print(message, file=sys.stderr)
    _audit(
        hook="gh-token-guard",
        decision="block",
        tool="Bash",
        reason="gh CLI without explicit GH_TOKEN",
        command_excerpt=command[:240],
    )
    return 2


def _disabled() -> bool:
    if os.environ.get("GH_TOKEN_GUARD_DISABLE") == "1":
        return True
    return is_bypassed("gh-token-guard")


def main() -> int:
    if _disabled():
        return 0
    if not should_run("gh-token-guard"):
        return 0
    data = read_hook_payload("gh-token-guard")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        return 0

    if GH_AUTH_SWITCH.search(mask_literal_text(command)):
        return _block(AUTH_SWITCH_MESSAGE, command)

    if not any(_needs_token(call) for call in invocations(command, "gh")):
        return 0

    return _block(f"{MISSING_TOKEN_MESSAGE}Command: {command}", command)


if __name__ == "__main__":
    sys.exit(main())

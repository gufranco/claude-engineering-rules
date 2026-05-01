#!/usr/bin/env python3
"""Block gh CLI commands that don't have GH_TOKEN set inline.

Prevents accidental use of the wrong GitHub account when multiple
accounts are configured. The global active account can change at
any time from another terminal, so every gh command must explicitly
set GH_TOKEN.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover
    def _audit(**_fields):  # type: ignore
        return None


# Patterns that indicate a gh CLI invocation
GH_COMMAND = re.compile(
    r"(?:^|&&|\|\||;|\|)\s*gh\s+"
)

# gh auth commands are exempt (needed to list accounts, get tokens)
GH_AUTH_EXEMPT = re.compile(
    r"(?:^|&&|\|\||;|\|)\s*gh\s+auth\s+"
)

# GH_TOKEN is set inline before the gh command
GH_TOKEN_SET = re.compile(
    r"GH_TOKEN=|export\s+GH_TOKEN="
)

# gh auth switch is always blocked
GH_AUTH_SWITCH = re.compile(
    r"\bgh\s+auth\s+switch\b"
)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    # Always block gh auth switch
    if GH_AUTH_SWITCH.search(command):
        print(
            "BLOCKED: gh auth switch changes the global active account "
            "and affects all terminals.\n"
            "Use GH_TOKEN=$(gh auth token --user <account>) gh <command> instead.\n"
            "Check the git remote to determine the correct account.\n"
            "See: standards/multi-account-cli.md"
        )
        _audit(hook="gh-token-guard", decision="block", tool="Bash", reason="gh CLI without explicit GH_TOKEN", command_excerpt=command[:240])
        sys.exit(2)

    # Skip if no gh command present
    if not GH_COMMAND.search(command):
        sys.exit(0)

    # Allow gh auth commands (e.g., gh auth token, gh auth status)
    # but only if ALL gh commands in the string are gh auth
    gh_calls = GH_COMMAND.findall(command)
    gh_auth_calls = GH_AUTH_EXEMPT.findall(command)
    if len(gh_calls) == len(gh_auth_calls):
        sys.exit(0)

    # Check if GH_TOKEN is set somewhere in the command
    if GH_TOKEN_SET.search(command):
        sys.exit(0)

    print(
        "BLOCKED: gh command without explicit GH_TOKEN.\n"
        "Multiple GitHub accounts are configured. The global active account "
        "can change from another terminal at any time.\n"
        "Prefix with: GH_TOKEN=$(gh auth token --user <account>) gh ...\n"
        "Or export it: export GH_TOKEN=$(gh auth token --user <account>)\n"
        "Check git remote get-url origin to determine the correct account.\n"
        "See: standards/multi-account-cli.md\n"
        f"Command: {command}"
    )
    _audit(hook="gh-token-guard", decision="block", tool="Bash", reason="gh CLI without explicit GH_TOKEN", command_excerpt=command[:240])
    sys.exit(2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Block glab CLI commands that don't have GITLAB_TOKEN set inline.

Prevents accidental use of the wrong GitLab account when multiple
instances or accounts are configured. The global config can change
at any time from another terminal, so every glab command must
explicitly set GITLAB_TOKEN and GITLAB_HOST.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

import json
import re
import sys


# Patterns that indicate a glab CLI invocation
GLAB_COMMAND = re.compile(
    r"(?:^|&&|\|\||;|\|)\s*glab\s+"
)

# glab auth commands are exempt (needed to check status, get tokens)
GLAB_AUTH_EXEMPT = re.compile(
    r"(?:^|&&|\|\||;|\|)\s*glab\s+auth\s+"
)

# GITLAB_TOKEN is set inline before the glab command
GITLAB_TOKEN_SET = re.compile(
    r"GITLAB_TOKEN=|export\s+GITLAB_TOKEN="
)

# glab auth login is always blocked (mutates global config)
GLAB_AUTH_LOGIN = re.compile(
    r"\bglab\s+auth\s+login\b"
)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("input", {}).get("command", "")
    if not command:
        sys.exit(0)

    # Always block glab auth login
    if GLAB_AUTH_LOGIN.search(command):
        print(
            "BLOCKED: glab auth login changes the global config "
            "and affects all terminals.\n"
            "Use GITLAB_TOKEN=<token> GITLAB_HOST=<host> glab <command> instead.\n"
            "Check the git remote to determine the correct instance."
        )
        sys.exit(2)

    # Skip if no glab command present
    if not GLAB_COMMAND.search(command):
        sys.exit(0)

    # Allow glab auth commands (e.g., glab auth status)
    # but only if ALL glab commands in the string are glab auth
    glab_calls = GLAB_COMMAND.findall(command)
    glab_auth_calls = GLAB_AUTH_EXEMPT.findall(command)
    if len(glab_calls) == len(glab_auth_calls):
        sys.exit(0)

    # Check if GITLAB_TOKEN is set somewhere in the command
    if GITLAB_TOKEN_SET.search(command):
        sys.exit(0)

    print(
        "BLOCKED: glab command without explicit GITLAB_TOKEN.\n"
        "Multiple GitLab instances may be configured. The global config "
        "can change from another terminal at any time.\n"
        "Prefix with: GITLAB_TOKEN=<token> GITLAB_HOST=<host> glab ...\n"
        "Or export them: export GITLAB_TOKEN=<token> GITLAB_HOST=<host>\n"
        "Check git remote get-url origin to determine the correct instance.\n"
        f"Command: {command}"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Block global AWS profile mutations.

`aws configure set` without `--profile` writes to the default profile in
`~/.aws/config`, silently changing what every other shell sees. The fix
is to scope the write with `--profile <name>` or to use `aws --profile`
on every call.

This hook hard-blocks `aws configure set ...` when no `--profile` flag
is present. Read-only `aws configure list` / `aws configure get` is
allowed. Bare `aws s3 ls` is allowed (it reads the current profile, not
mutates it); the agent is still expected to set `--profile` or
`AWS_PROFILE` for clarity per `standards/multi-account-cli.md`.

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


# `aws configure set ...` — writes to AWS config. Block when no --profile.
AWS_CONFIGURE_SET = re.compile(
    r"\baws\s+configure\s+set\b"
)

# Profile flag/env present in the same command segment.
AWS_PROFILE_PRESENT = re.compile(
    r"--profile[\s=]\S+|AWS_PROFILE=\S+"
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if AWS_CONFIGURE_SET.search(command) and not AWS_PROFILE_PRESENT.search(command):
        print(
            "BLOCKED: `aws configure set ...` without `--profile <name>` "
            "writes to the default AWS profile and affects every shell.\n"
            "Scope the write: `aws configure set --profile <name> ...`\n"
            "Or use the per-command form on actual aws calls: "
            "`aws --profile <name> ...` or `AWS_PROFILE=<name> aws ...`\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}"
        )
        _audit(hook="aws-profile-guard", decision="block", tool="Bash",
               reason="aws configure set without --profile",
               command_excerpt=command)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

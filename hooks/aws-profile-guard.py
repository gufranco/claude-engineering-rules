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

import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.cli_invocations import Invocation, invocations  # noqa: E402


def _configures_without_profile(call: Invocation) -> bool:
    args = list(call.args)
    sets = any(args[i : i + 2] == ["configure", "set"] for i in range(len(args)))
    scoped = "AWS_PROFILE" in call.assigned or any(
        arg == "--profile" or arg.startswith("--profile=") for arg in args
    )
    return sets and not scoped


def main() -> None:
    if os.environ.get("AWS_PROFILE_GUARD_DISABLE") == "1":
        _sys.exit(0)
    if is_bypassed("aws-profile-guard"):
        _sys.exit(0)
    if not should_run("aws-profile-guard"):
        _sys.exit(0)
    data = read_hook_payload("aws-profile-guard")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if any(_configures_without_profile(c) for c in invocations(command, "aws")):
        print(
            "BLOCKED: `aws configure set ...` without `--profile <name>` "
            "writes to the default AWS profile and affects every shell.\n"
            "Scope the write: `aws configure set --profile <name> ...`\n"
            "Or use the per-command form on actual aws calls: "
            "`aws --profile <name> ...` or `AWS_PROFILE=<name> aws ...`\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}",
            file=sys.stderr,
        )
        _audit(
            hook="aws-profile-guard",
            decision="block",
            tool="Bash",
            reason="aws configure set without --profile",
            command_excerpt=command,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

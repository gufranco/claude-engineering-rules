#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.cli_invocations import Invocation, invocations  # noqa: E402


HOOK_NAME = "aws-profile-guard"


def _configures_without_profile(call: Invocation) -> bool:
    args = list(call.args)
    sets = any(args[i : i + 2] == ["configure", "set"] for i in range(len(args)))
    scoped = "AWS_PROFILE" in call.assigned or any(
        arg == "--profile" or arg.startswith("--profile=") for arg in args
    )
    return sets and not scoped


def _skipped() -> bool:
    if os.environ.get("AWS_PROFILE_GUARD_DISABLE") == "1":
        return True
    if is_bypassed(HOOK_NAME):
        return True
    return not should_run(HOOK_NAME)


def _block(command: str) -> None:
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
        hook=HOOK_NAME,
        decision="block",
        tool="Bash",
        reason="aws configure set without --profile",
        command_excerpt=command,
    )
    sys.exit(2)


def main() -> None:
    if _skipped():
        sys.exit(0)
    data = read_hook_payload(HOOK_NAME)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if any(_configures_without_profile(c) for c in invocations(command, "aws")):
        _block(command)

    sys.exit(0)


if __name__ == "__main__":
    main()

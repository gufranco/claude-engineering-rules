#!/usr/bin/env python3
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


GCLOUD_CONFIG_ACTIVATE = re.compile(
    r"\bgcloud\s+config\s+configurations\s+activate\s+(?!--help\b|-h\b)\S+"
)


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.cli_invocations import Invocation, invocations  # noqa: E402


def _sets_without_configuration(call: Invocation) -> bool:
    args = list(call.args)
    sets = any(args[i : i + 2] == ["config", "set"] for i in range(len(args)))
    scoped = "CLOUDSDK_ACTIVE_CONFIG_NAME" in call.assigned or any(
        arg == "--configuration" or arg.startswith("--configuration=") for arg in args
    )
    return sets and not scoped


ACTIVATE_MESSAGE = (
    "BLOCKED: `gcloud config configurations activate <name>` "
    "switches the active gcloud configuration globally and "
    "affects every shell.\n"
    "Use the per-command form: "
    "`gcloud --configuration=<name> ...`\n"
    "Or pass `--account=<email>` and `--project=<id>` directly "
    "on each gcloud call.\n"
    "See: standards/multi-account-cli.md\n"
)

SET_MESSAGE = (
    "BLOCKED: `gcloud config set ...` without "
    "`--configuration=<name>` writes to the active gcloud "
    "configuration and affects every shell.\n"
    "Scope the write: "
    "`gcloud config set --configuration=<name> <key> <value>`\n"
    "Or use the per-command form on actual gcloud calls: "
    "`gcloud --account=<email> --project=<id> ...`\n"
    "See: standards/multi-account-cli.md\n"
)


def _should_skip() -> bool:
    if os.environ.get("GCLOUD_CONFIG_GUARD_DISABLE") == "1":
        return True
    if is_bypassed("gcloud-config-guard"):
        return True
    return not should_run("gcloud-config-guard")


def _block(message: str, command: str) -> None:
    print(f"{message}Command: {command}", file=sys.stderr)
    _audit(
        hook="gcloud-config-guard",
        decision="block",
        tool="Bash",
        reason="gcloud config global mutation",
        command_excerpt=command[:240],
    )
    sys.exit(2)


def main() -> None:
    if _should_skip():
        sys.exit(0)
    data = read_hook_payload("gcloud-config-guard")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if GCLOUD_CONFIG_ACTIVATE.search(command):
        _block(ACTIVATE_MESSAGE, command)

    if any(_sets_without_configuration(c) for c in invocations(command, "gcloud")):
        _block(SET_MESSAGE, command)

    sys.exit(0)


if __name__ == "__main__":
    main()

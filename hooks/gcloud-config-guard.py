#!/usr/bin/env python3
"""Block global gcloud config mutations.

`gcloud config set account ...`, `gcloud config set project ...`, and
`gcloud config configurations activate <name>` all mutate the active
gcloud configuration in `~/.config/gcloud/`. Every other shell on the
machine immediately sees the change, breaking parallel sessions that
were targeting a different account or project.

The fix is to use per-command flags on every call:
- `gcloud --account=<email> ...`
- `gcloud --project=<id> ...`
- `gcloud --configuration=<name> ...`

Or scope a `config set` write with `--configuration=<name>` so it
writes to a named configuration instead of the active one.

This hook hard-blocks `gcloud config set ...` and `gcloud config
configurations activate ...` when no `--configuration=<name>` flag
is present. Read-only `gcloud config list`, `gcloud config get`,
and `gcloud config configurations list` are allowed.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


GCLOUD_CONFIG_ACTIVATE = re.compile(
    r"\bgcloud\s+config\s+configurations\s+activate\s+(?!--help\b|-h\b)\S+"
)


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


def _sets_without_configuration(call: Invocation) -> bool:
    args = list(call.args)
    sets = any(args[i : i + 2] == ["config", "set"] for i in range(len(args)))
    scoped = "CLOUDSDK_ACTIVE_CONFIG_NAME" in call.assigned or any(
        arg == "--configuration" or arg.startswith("--configuration=") for arg in args
    )
    return sets and not scoped


def main() -> None:
    if os.environ.get("GCLOUD_CONFIG_GUARD_DISABLE") == "1":
        _sys.exit(0)
    if is_bypassed("gcloud-config-guard"):
        _sys.exit(0)
    if not should_run("gcloud-config-guard"):
        _sys.exit(0)
    data = read_hook_payload("gcloud-config-guard")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if GCLOUD_CONFIG_ACTIVATE.search(command):
        print(
            "BLOCKED: `gcloud config configurations activate <name>` "
            "switches the active gcloud configuration globally and "
            "affects every shell.\n"
            "Use the per-command form: "
            "`gcloud --configuration=<name> ...`\n"
            "Or pass `--account=<email>` and `--project=<id>` directly "
            "on each gcloud call.\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}",
            file=sys.stderr,
        )
        _audit(
            hook="gcloud-config-guard",
            decision="block",
            tool="Bash",
            reason="gcloud config global mutation",
            command_excerpt=command[:240],
        )
        sys.exit(2)

    if any(_sets_without_configuration(c) for c in invocations(command, "gcloud")):
        print(
            "BLOCKED: `gcloud config set ...` without "
            "`--configuration=<name>` writes to the active gcloud "
            "configuration and affects every shell.\n"
            "Scope the write: "
            "`gcloud config set --configuration=<name> <key> <value>`\n"
            "Or use the per-command form on actual gcloud calls: "
            "`gcloud --account=<email> --project=<id> ...`\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}",
            file=sys.stderr,
        )
        _audit(
            hook="gcloud-config-guard",
            decision="block",
            tool="Bash",
            reason="gcloud config global mutation",
            command_excerpt=command[:240],
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

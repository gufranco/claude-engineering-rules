#!/usr/bin/env python3
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


TF_GLOBAL_OPTIONS = r"(?:\s+-[\w-]+(?:=\S+)?)*"

TF_WORKSPACE_SELECT = re.compile(
    r"\bterraform" + TF_GLOBAL_OPTIONS + r"\s+workspace\s+select\s+(?!--help\b|-h\b)\S+"
)

TF_WORKSPACE_NEW = re.compile(
    r"\bterraform" + TF_GLOBAL_OPTIONS + r"\s+workspace\s+new\s+(?!--help\b|-h\b)\S+"
)


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def _exit_when_disabled() -> None:
    if os.environ.get("TERRAFORM_WORKSPACE_GUARD_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("terraform-workspace-guard"):
        sys.exit(0)
    if not should_run("terraform-workspace-guard"):
        sys.exit(0)


def _block(command: str) -> None:
    print(
        "BLOCKED: `terraform workspace select|new <name>` writes the "
        "active workspace to `.terraform/environment` and affects "
        "every shell running terraform in this directory.\n"
        "Use the per-command form: "
        "`TF_WORKSPACE=<name> terraform plan|apply ...`\n"
        "TF_WORKSPACE keeps `.terraform/environment` untouched, so "
        "parallel shells targeting different workspaces stay "
        "isolated.\n"
        "See: standards/multi-account-cli.md\n"
        f"Command: {command}",
        file=sys.stderr,
    )
    _audit(
        hook="terraform-workspace-guard",
        decision="block",
        tool="Bash",
        reason="terraform workspace global switch",
        command_excerpt=command[:240],
    )
    sys.exit(2)


def main() -> None:
    _exit_when_disabled()
    data = read_hook_payload("terraform-workspace-guard")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if TF_WORKSPACE_SELECT.search(command) or TF_WORKSPACE_NEW.search(command):
        _block(command)

    sys.exit(0)


if __name__ == "__main__":
    main()

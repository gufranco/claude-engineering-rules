#!/usr/bin/env python3
"""Block global Terraform workspace switches.

`terraform workspace select <name>` and `terraform workspace new <name>`
both write the active workspace to `.terraform/environment` in the
working directory. Any other shell or process running terraform in the
same directory will silently target the new workspace.

The fix is to set `TF_WORKSPACE=<name>` per command. With that env var
set, terraform uses the named workspace without writing to
`.terraform/environment`, so parallel shells stay isolated.

This hook hard-blocks `terraform workspace select` and
`terraform workspace new`. Read-only `terraform workspace list` and
`terraform workspace show` are allowed.

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


# `terraform workspace select <name>` — switches active workspace.
TF_WORKSPACE_SELECT = re.compile(
    r"\bterraform\s+workspace\s+select\s+(?!--help\b|-h\b)\S+"
)

# `terraform workspace new <name>` — creates and switches to new workspace.
TF_WORKSPACE_NEW = re.compile(
    r"\bterraform\s+workspace\s+new\s+(?!--help\b|-h\b)\S+"
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if TF_WORKSPACE_SELECT.search(command) or TF_WORKSPACE_NEW.search(command):
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
            f"Command: {command}"
        )
        _audit(hook="terraform-workspace-guard", decision="block", tool="Bash", reason="terraform workspace global switch", command_excerpt=command[:240])
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

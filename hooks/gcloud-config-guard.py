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

import json
import re
import sys


# `gcloud config set <key> <value>` — writes to active configuration.
GCLOUD_CONFIG_SET = re.compile(
    r"\bgcloud\s+config\s+set\b"
)

# `gcloud config configurations activate <name>` — switches active config.
GCLOUD_CONFIG_ACTIVATE = re.compile(
    r"\bgcloud\s+config\s+configurations\s+activate\s+(?!--help\b|-h\b)\S+"
)

# `--configuration=<name>` flag scopes the write to a named configuration
# instead of the active one. Allowed even on `gcloud config set`.
GCLOUD_CONFIGURATION_FLAG = re.compile(
    r"--configuration[\s=]\S+"
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("input", {}).get("command", "")
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
            f"Command: {command}"
        )
        sys.exit(2)

    if GCLOUD_CONFIG_SET.search(command) and not GCLOUD_CONFIGURATION_FLAG.search(command):
        print(
            "BLOCKED: `gcloud config set ...` without "
            "`--configuration=<name>` writes to the active gcloud "
            "configuration and affects every shell.\n"
            "Scope the write: "
            "`gcloud config set --configuration=<name> <key> <value>`\n"
            "Or use the per-command form on actual gcloud calls: "
            "`gcloud --account=<email> --project=<id> ...`\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}"
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

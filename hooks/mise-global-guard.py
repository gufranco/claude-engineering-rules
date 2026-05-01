#!/usr/bin/env python3
"""Block global mise tool mutations.

`mise use --global <tool>@<version>` and `mise use -g <tool>@<version>`
write to `~/.config/mise/config.toml`, the shared global config every
shell reads when no project-local `.mise.toml` or `.tool-versions`
applies. Mutating it from one terminal silently changes the fallback
runtime for every other shell on the machine.

Unlike other multi-account CLIs, mise defaults to project-local writes:
plain `mise use <tool>@<version>` updates the cwd's `.mise.toml`. The
`--global`/`-g` flag is an explicit opt-in to the shared file. This
hook hard-blocks that opt-in.

Allowed:
- `mise use <tool>@<version>` (writes to project-local `.mise.toml`)
- `mise install`, `mise current`, `mise ls`, `mise which`, `mise where`
- `mise exec ...` / `mise x ...` (per-command, no global mutation)
- `mise run ...`

Blocked:
- `mise use --global ...` / `mise use -g ...`
- `mise unuse --global ...` / `mise unuse -g ...`

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

import json
import re
import sys


# `mise use --global ...` or `mise use -g ...` — writes to ~/.config/mise/config.toml
MISE_USE_GLOBAL = re.compile(
    r"\bmise\s+use\b[^|;&]*\s(?:--global\b|-g\b)"
)

# `mise unuse --global ...` or `mise unuse -g ...` — removes from global config
MISE_UNUSE_GLOBAL = re.compile(
    r"\bmise\s+unuse\b[^|;&]*\s(?:--global\b|-g\b)"
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if MISE_USE_GLOBAL.search(command):
        print(
            "BLOCKED: `mise use --global ...` writes to "
            "`~/.config/mise/config.toml` and affects every shell that "
            "falls back to the global config.\n"
            "Pin the version per project: "
            "`mise use <tool>@<version>` (writes to `.mise.toml` in cwd).\n"
            "Or run a one-off command without mutation: "
            "`mise exec <tool>@<version> -- <command>`.\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}"
        )
        sys.exit(2)

    if MISE_UNUSE_GLOBAL.search(command):
        print(
            "BLOCKED: `mise unuse --global ...` mutates "
            "`~/.config/mise/config.toml` and affects every shell.\n"
            "Edit the project's `.mise.toml` or `.tool-versions` to remove "
            "the tool, or run `mise unuse <tool>` (no `--global`) inside "
            "the project directory.\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}"
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Block `docker context use` to prevent global Docker context mutation.

Multiple Docker contexts may be configured (Colima profiles, remote hosts,
Docker Desktop). The active context is shared across every shell, so a
`docker context use <name>` in one terminal silently breaks parallel
sessions targeting a different context.

The fix is to use the per-command `--context <name>` flag, or set
`DOCKER_CONTEXT=<name>` / `DOCKER_HOST=<socket>` for the duration of a
script. This hook hard-blocks the global mutation command and points to
`standards/multi-account-cli.md` for the per-command form.

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


# `docker context use <name>` — global mutation. Block.
# Excludes `docker context use --help` and `docker context use -h`.
DOCKER_CONTEXT_USE = re.compile(
    r"\bdocker\s+context\s+use\s+(?!--help\b|-h\b)[\w\.\-]+"
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if DOCKER_CONTEXT_USE.search(command):
        print(
            "BLOCKED: `docker context use` mutates the active Docker context "
            "for every shell on this machine.\n"
            "Use the per-command flag instead: `docker --context <name> ...`\n"
            "Or set the env var for the script: "
            "`export DOCKER_CONTEXT=<name>` then run docker commands.\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}"
        )
        _audit(hook="docker-context-guard", decision="block", tool="Bash", reason="docker context use without scope", command_excerpt=command[:240])
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

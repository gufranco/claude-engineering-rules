#!/usr/bin/env python3
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


MISE_USE_GLOBAL = re.compile(r"\bmise\s+use\b[^|;&]*\s(?:--global\b|-g\b)")

MISE_UNUSE_GLOBAL = re.compile(r"\bmise\s+unuse\b[^|;&]*\s(?:--global\b|-g\b)")


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


USE_GLOBAL_MESSAGE = (
    "BLOCKED: `mise use --global ...` writes to "
    "`~/.config/mise/config.toml` and affects every shell that "
    "falls back to the global config.\n"
    "Pin the version per project: "
    "`mise use <tool>@<version>` (writes to `.mise.toml` in cwd).\n"
    "Or run a one-off command without mutation: "
    "`mise exec <tool>@<version> -- <command>`.\n"
    "See: standards/multi-account-cli.md\n"
)
UNUSE_GLOBAL_MESSAGE = (
    "BLOCKED: `mise unuse --global ...` mutates "
    "`~/.config/mise/config.toml` and affects every shell.\n"
    "Edit the project's `.mise.toml` or `.tool-versions` to remove "
    "the tool, or run `mise unuse <tool>` (no `--global`) inside "
    "the project directory.\n"
    "See: standards/multi-account-cli.md\n"
)


def _block(message: str, command: str) -> None:
    print(f"{message}Command: {command}", file=sys.stderr)
    _audit(
        hook="mise-global-guard",
        decision="block",
        tool="Bash",
        reason="mise global tool mutation",
        command_excerpt=command[:240],
    )
    sys.exit(2)


def _exit_if_disabled() -> None:
    if os.environ.get("MISE_GLOBAL_GUARD_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("mise-global-guard"):
        sys.exit(0)
    if not should_run("mise-global-guard"):
        sys.exit(0)


def main() -> None:
    _exit_if_disabled()
    data = read_hook_payload("mise-global-guard")
    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)
    if MISE_USE_GLOBAL.search(command):
        _block(USE_GLOBAL_MESSAGE, command)
    if MISE_UNUSE_GLOBAL.search(command):
        _block(UNUSE_GLOBAL_MESSAGE, command)
    sys.exit(0)


if __name__ == "__main__":
    main()

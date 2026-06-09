#!/usr/bin/env python3
"""Block cp/mv/rm invocations that may prompt interactively and hang.

On macOS, the default shell often aliases `rm` to `rm -i`, `cp` to `cp -i`,
and `mv` to `mv -i`. When an agent runs one of these against an existing
path, the shell prompts for confirmation, the agent has no stdin, and the
command hangs until the harness timeout.

The fix: require an explicit `-f` flag on cp/mv/rm. The user can still bypass
for the rare legitimate interactive use with INTERACTIVE_CMD_DISABLE=1.

Triggers PreToolUse on Bash. Exit 0 = allow, exit 2 = block.

Bypass: INTERACTIVE_CMD_DISABLE=1 in the parent shell.

Closes a gap left by dangerous-command-blocker.py.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


# Match the bare command name at command boundaries: start, ;, &&, ||, |, &
COMMAND_BOUNDARY = r"(?:^|[;&|]\s*|&&\s*|\|\|\s*)"

# Commands that prompt interactively when -i is the default alias
INTERACTIVE_PRONE = ("rm", "cp", "mv")

from _lib.bypass import is_bypassed  # noqa: E402



def split_commands(command: str) -> list[str]:
    """Split a bash command line by shell separators ; && || | &."""
    # Keep the boundary cheap; not aiming for full bash parsing
    parts = re.split(r"\s*(?:;|&&|\|\||\||&)\s*", command)
    return [p.strip() for p in parts if p.strip()]


def has_force_flag(tokens: list[str]) -> bool:
    """Check if any token expresses --force or -f (including combined like -rf)."""
    for tok in tokens[1:]:
        if not tok.startswith("-"):
            continue
        if tok == "--force":
            return True
        # Skip long flags that are not --force
        if tok.startswith("--"):
            continue
        # Short flags: -f, -rf, -fr, -frv, ...
        if "f" in tok[1:]:
            return True
    return False


def is_blocked(command: str) -> tuple[bool, str]:
    """Return (blocked, reason). Reason includes the command name."""
    for sub in split_commands(command):
        try:
            tokens = shlex.split(sub)
        except ValueError:
            # Unparseable shell - let other hooks handle
            continue
        if not tokens:
            continue
        # Resolve the actual command name, ignoring leading env vars or `command`
        i = 0
        while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
            i += 1
        if i >= len(tokens):
            continue
        head = tokens[i]
        if head == "command" and i + 1 < len(tokens):
            head = tokens[i + 1]
            i += 1
        # Strip path prefix (e.g., /bin/rm)
        base = os.path.basename(head)
        if base not in INTERACTIVE_PRONE:
            continue
        # Construct the effective arg list starting from the command itself
        effective = tokens[i:]
        if not has_force_flag(effective):
            return True, base
    return False, ""


def emit_block(reason: str, command: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stderr.write(reason)
    _audit(
        hook="interactive-cmd-blocker",
        decision="block",
        decision_class="block",
        reason=reason[:200],
        tool="Bash",
        command_excerpt=command[:200],
    )
    sys.exit(2)


def main() -> int:
    if os.environ.get("INTERACTIVE_CMD_DISABLE") == "1":
        return 0
    if is_bypassed("interactive-cmd-blocker"):
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if data.get("tool_name") != "Bash":
        return 0

    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    blocked, base = is_blocked(command)
    if not blocked:
        return 0

    reason = (
        f"BLOCKED: `{base}` invoked without `-f`. On macOS this often hangs "
        f"because the default alias adds `-i` and prompts for confirmation "
        f"that the agent cannot answer.\n"
        f"Fix: add `-f` (e.g. `{base} -f <path>` or `{base} -rf <path>` for "
        f"directories).\n"
        f"Bypass (one-off): set INTERACTIVE_CMD_DISABLE=1 in parent shell."
    )
    emit_block(reason, command)
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())

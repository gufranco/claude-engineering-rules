#!/usr/bin/env python3
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


DOCKER_CONTEXT_USE = re.compile(
    r"\bdocker\s+context\s+use\s+(?!--help\b|-h\b)[\w\.\-]+"
)


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


HOOK_NAME = "docker-context-guard"
COMMAND_EXCERPT_LIMIT = 240


def _skipped() -> bool:
    if os.environ.get("DOCKER_CONTEXT_GUARD_DISABLE") == "1":
        return True
    if is_bypassed(HOOK_NAME):
        return True
    return not should_run(HOOK_NAME)


def _block(command: str) -> None:
    print(
        "BLOCKED: `docker context use` mutates the active Docker context "
        "for every shell on this machine.\n"
        "Use the per-command flag instead: `docker --context <name> ...`\n"
        "Or set the env var for the script: "
        "`export DOCKER_CONTEXT=<name>` then run docker commands.\n"
        "See: standards/multi-account-cli.md\n"
        f"Command: {command}",
        file=sys.stderr,
    )
    _audit(
        hook=HOOK_NAME,
        decision="block",
        tool="Bash",
        reason="docker context use without scope",
        command_excerpt=command[:COMMAND_EXCERPT_LIMIT],
    )
    sys.exit(2)


def main() -> None:
    if _skipped():
        sys.exit(0)
    data = read_hook_payload(HOOK_NAME)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if DOCKER_CONTEXT_USE.search(command):
        _block(command)

    sys.exit(0)


if __name__ == "__main__":
    main()

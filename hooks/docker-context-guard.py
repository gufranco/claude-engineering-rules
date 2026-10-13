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


def main() -> None:
    if os.environ.get("DOCKER_CONTEXT_GUARD_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("docker-context-guard"):
        sys.exit(0)
    if not should_run("docker-context-guard"):
        sys.exit(0)
    data = read_hook_payload("docker-context-guard")

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
            f"Command: {command}",
            file=sys.stderr,
        )
        _audit(
            hook="docker-context-guard",
            decision="block",
            tool="Bash",
            reason="docker context use without scope",
            command_excerpt=command[:240],
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

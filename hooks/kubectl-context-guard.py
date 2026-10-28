#!/usr/bin/env python3
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


KUBECTL_USE_CONTEXT = re.compile(
    r"\bkubectl\s+config\s+use-context\s+(?!--help\b|-h\b)[\w\.\-]+"
)

KUBECTX_SWITCH = re.compile(
    r"(?:^|&&|\|\||;|\||\n)\s*kubectx\s+(?!--help\b|-h\b|--?$)[\w\.\-]+"
)
KUBECTX_PREVIOUS = re.compile(
    r"(?:^|&&|\|\||;|\||\n)\s*kubectx\s+-\s*(?:&&|\|\||;|\||\n|$)"
)


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


USE_CONTEXT_MESSAGE = (
    "BLOCKED: `kubectl config use-context` mutates the active "
    "Kubernetes context for every shell.\n"
)

KUBECTX_MESSAGE = (
    "BLOCKED: `kubectx <name>` calls `kubectl config use-context` "
    "and mutates the active context globally.\n"
)

ALTERNATIVES_MESSAGE = (
    "Use the per-command flag instead: `kubectl --context <name> ...`\n"
    "Or set the env var: `export KUBECONFIG=<path>` then run kubectl.\n"
    "See: standards/multi-account-cli.md\n"
)


def _should_skip() -> bool:
    if os.environ.get("KUBECTL_CONTEXT_GUARD_DISABLE") == "1":
        return True
    if is_bypassed("kubectl-context-guard"):
        return True
    return not should_run("kubectl-context-guard")


def _block(headline: str, command: str) -> None:
    print(f"{headline}{ALTERNATIVES_MESSAGE}Command: {command}", file=sys.stderr)
    _audit(
        hook="kubectl-context-guard",
        decision="block",
        tool="Bash",
        reason="kubectl context global switch",
        command_excerpt=command[:240],
    )
    sys.exit(2)


def main() -> None:
    if _should_skip():
        sys.exit(0)
    data = read_hook_payload("kubectl-context-guard")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if KUBECTL_USE_CONTEXT.search(command):
        _block(USE_CONTEXT_MESSAGE, command)

    if KUBECTX_SWITCH.search(command) or KUBECTX_PREVIOUS.search(command):
        _block(KUBECTX_MESSAGE, command)

    sys.exit(0)


if __name__ == "__main__":
    main()

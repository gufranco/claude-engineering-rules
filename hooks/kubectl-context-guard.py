#!/usr/bin/env python3
"""Block global kubectl context switches.

The active Kubernetes context is shared across every shell. A
`kubectl config use-context <name>` (or its `kubectx <name>` wrapper)
silently breaks parallel terminals targeting a different cluster.

The fix is to use the per-command `--context <name>` flag, or set
`KUBECONFIG=<path>` for the duration of a script. This hook hard-blocks
the global mutation commands and points to
`standards/multi-account-cli.md` for the per-command form.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

import json
import re
import sys


# `kubectl config use-context <name>` — global mutation. Block.
KUBECTL_USE_CONTEXT = re.compile(
    r"\bkubectl\s+config\s+use-context\s+(?!--help\b|-h\b)[\w\.\-]+"
)

# `kubectx <name>` — wrapper around use-context. Block when an arg is given.
# `kubectx` alone (no arg) lists contexts and is allowed.
# `kubectx -` switches to previous context (also a global mutation).
KUBECTX_SWITCH = re.compile(
    r"(?:^|&&|\|\||;|\|)\s*kubectx\s+(?!--help\b|-h\b|--?$)[\w\.\-]+"
)
KUBECTX_PREVIOUS = re.compile(
    r"(?:^|&&|\|\||;|\|)\s*kubectx\s+-\s*(?:&&|\|\||;|\||$)"
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    if KUBECTL_USE_CONTEXT.search(command):
        print(
            "BLOCKED: `kubectl config use-context` mutates the active "
            "Kubernetes context for every shell.\n"
            "Use the per-command flag instead: `kubectl --context <name> ...`\n"
            "Or set the env var: `export KUBECONFIG=<path>` then run kubectl.\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}"
        )
        sys.exit(2)

    if KUBECTX_SWITCH.search(command) or KUBECTX_PREVIOUS.search(command):
        print(
            "BLOCKED: `kubectx <name>` calls `kubectl config use-context` "
            "and mutates the active context globally.\n"
            "Use the per-command flag instead: `kubectl --context <name> ...`\n"
            "Or set the env var: `export KUBECONFIG=<path>` then run kubectl.\n"
            "See: standards/multi-account-cli.md\n"
            f"Command: {command}"
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

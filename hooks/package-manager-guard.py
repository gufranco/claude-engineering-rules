#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.audit_log import record as audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.output import block  # noqa: E402
from _lib.package_manager_rules import violations  # noqa: E402

HOOK = "package-manager-guard"
ENV_DISABLE = "PACKAGE_MANAGER_GUARD_DISABLE"
BLOCK_EXIT = 2
EXCERPT_LIMIT = 240

WHY = (
    "Every project installs with pnpm and uv against a committed lockfile. npm,\n"
    "npx and yarn resolve outside pnpm-lock.yaml, and pip writes into whatever\n"
    "interpreter is first on PATH, so the result differs from CI and from the\n"
    "next machine."
)

FIX = (
    "Run the pnpm or uv command named above. A project still on npm or yarn\n"
    "migrates with `pnpm import`, then deletes package-lock.json or yarn.lock.\n"
    "A Python project without uv.lock starts with `uv init` or `uv add`."
)

BYPASS_WHEN = "The command runs inside a project the owner keeps on npm, yarn or pip."


def _skipped() -> bool:
    if not should_run(HOOK):
        return True
    if os.environ.get(ENV_DISABLE) == "1":
        audit(hook=HOOK, decision="bypass", bypass_env=ENV_DISABLE)
        return True
    return is_bypassed(HOOK)


def main() -> int:
    if _skipped():
        return 0
    payload = read_hook_payload(HOOK)
    command = str(tool_input_of(payload).get("command") or "")
    found = violations(command) if payload.get("tool_name") == "Bash" else []
    if not found:
        return 0
    print(
        block(
            hook=HOOK,
            rule_anchor="standards/shell-and-tools.md",
            detected="\n".join(found),
            why=WHY,
            fix=FIX,
            bypass_when=BYPASS_WHEN,
            decision="FIX-AND-RETRY",
            env_var=ENV_DISABLE,
        ),
        file=sys.stderr,
    )
    audit(
        hook=HOOK,
        decision="block",
        tool="Bash",
        reason="npm, npx, yarn or pip",
        command_excerpt=command[:EXCERPT_LIMIT],
    )
    return BLOCK_EXIT


if __name__ == "__main__":
    sys.exit(main())

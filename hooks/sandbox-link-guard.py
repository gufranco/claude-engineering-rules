#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.audit_log import record as _audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.output import block  # noqa: E402
from _lib.sandbox_links import Link, escaping_links  # noqa: E402

HOOK = "sandbox-link-guard"
BYPASS_ENV = "SANDBOX_LINK_DISABLE"
RULE_ANCHOR = "rules/agent-operating-limits.md"
WHY = (
    "A sandbox that reaches a real directory through a link is not a sandbox. Every "
    "write through a path that crosses the link, including a write a script makes "
    "inside a folder it just linked, lands in the real tree, and stubbed commands do "
    "not help because ln, mv, cp and redirection are not stubbed. When the temp dir "
    "is deleted, links the run left in the real tree dangle."
)
FIX = (
    "Give the sandbox copies, never links:\n"
    '  git clone <repo> "$S/home/.dotfiles"      a repository\n'
    '  git worktree add "$S/tree" HEAD           a checkout of the current repo\n'
    '  cp -R <real-path> "$S/..."               anything else\n'
    "Before the run, list every symlink in the sandbox and stop if one resolves\n"
    "outside it. After the run, prove nothing outside changed: snapshot the real\n"
    "tree with ignored files, such as `find <real> -newer <marker>`, and search it\n"
    "for links into the temp dir. A clean git status is not proof."
)
BYPASS_WHEN = (
    "The link is read-only by construction and nothing in the run writes through it."
)


def _report(links: list[Link]) -> str:
    rows = [f"real: {link.source}\n  linked at: {link.destination}" for link in links]
    return "\n".join(["A temp-dir link would reach a real path:", *rows])


def _command(payload: dict[str, object]) -> str:
    command = tool_input_of(payload).get("command")
    is_bash = payload.get("tool_name") == "Bash"
    return command if is_bash and isinstance(command, str) else ""


def main() -> int:
    if not should_run(HOOK) or os.environ.get(BYPASS_ENV) == "1" or is_bypassed(HOOK):
        return 0
    payload = read_hook_payload(HOOK)
    cwd = str(payload.get("cwd") or os.getcwd())
    links = escaping_links(_command(payload), cwd, os.environ)
    if not links:
        return 0
    print(
        block(
            hook=HOOK,
            rule_anchor=RULE_ANCHOR,
            detected=_report(links),
            why=WHY,
            fix=FIX,
            bypass_when=BYPASS_WHEN,
            decision="FIX-AND-RETRY",
            env_var=BYPASS_ENV,
        ),
        file=sys.stderr,
    )
    _audit(hook=HOOK, decision="block", reason="temp link to a real path")
    return 2


if __name__ == "__main__":
    sys.exit(main())

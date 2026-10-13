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


RESOLVE_MUTATION = re.compile(r"\bresolveReviewThread\b")
FORGE_API = re.compile(r"\b(?:gh|glab)\s+api\b")
GLAB_RESOLVE = re.compile(
    r"(?:gh|glab)\s+api[^\n]*?-X\s+PUT[^\n]*?resolved=true",
    re.IGNORECASE,
)
LINE_CONTINUATION = re.compile(r"\\\n")
NON_FORGE_SINKS = frozenset({"cat", "tee", "git"})
FOR_LOOP_PATTERN = re.compile(r"\bfor\s+\w+\s+in\b")
WHILE_LOOP_PATTERN = re.compile(r"\bwhile\s+")
XARGS_PATTERN = re.compile(r"\|\s*xargs\b")


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.shell_segments import strip_data_heredoc_bodies  # noqa: E402


def main() -> None:
    if not should_run("bulk-resolve-blocker"):
        sys.exit(0)
    if os.environ.get("BULK_RESOLVE_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("bulk-resolve-blocker"):
        sys.exit(0)

    data = read_hook_payload("bulk-resolve-blocker")

    tool_input = data.get("tool_input", data.get("input", {}))
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    joined = LINE_CONTINUATION.sub(
        " ", strip_data_heredoc_bodies(command, NON_FORGE_SINKS)
    )
    github_calls = (
        len(RESOLVE_MUTATION.findall(joined)) if FORGE_API.search(joined) else 0
    )
    gitlab_calls = len(GLAB_RESOLVE.findall(joined))
    occurrences = github_calls + gitlab_calls

    if occurrences == 0:
        sys.exit(0)

    in_loop = bool(
        FOR_LOOP_PATTERN.search(command)
        or WHILE_LOOP_PATTERN.search(command)
        or XARGS_PATTERN.search(command)
    )

    if occurrences > 1 or in_loop:
        platform = "GitHub" if github_calls else "GitLab"
        print(
            "BLOCKED: bulk resolution of review threads.\n"
            "Each review thread must be resolved individually after its own "
            "action. Bulk-resolving erases the reviewer's ability to verify "
            "which concerns were addressed.\n"
            "Either run one resolve mutation per thread, or set "
            "BULK_RESOLVE_DISABLE=1 in the environment if you have manually "
            "verified every thread.\n"
            f"Detected {occurrences} {platform} resolve call(s) in the "
            f"command{' inside a loop' if in_loop else ''}.\n"
            f"Command: {command[:240]}",
            file=sys.stderr,
        )
        _audit(
            hook="bulk-resolve-blocker",
            decision="block",
            tool="Bash",
            reason="bulk-resolve detected",
            occurrences=occurrences,
            in_loop=in_loop,
            command_excerpt=command[:240],
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

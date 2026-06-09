#!/usr/bin/env python3
"""Block per-file source fetching from remote repos (gh / GitLab / raw URLs).

When more than two source files from the same remote repo are needed, the
correct workflow is a shallow clone into a temp directory followed by local
Read/Grep/Glob. Fetching one file at a time through `gh api .../contents`,
`gh repo view <o>/<r> <path>`, `glab api .../repository/files/<path>`, or
`raw.githubusercontent.com` is slow, rate-limited, and returns base64-wrapped
content that has to be decoded per call.

This hook blocks the most common per-file fetch patterns at PreToolUse on
Bash. Carve-outs (issues, PRs, diffs, search, single README probe, repo
metadata view, git clone itself) remain allowed.

Triggers PreToolUse on Bash. Exit 0 = allow, exit 2 = block.

Bypass: REPO_FETCH_DISABLE=1 in the parent shell (export, not inline).

Enforces: rules/repo-analysis.md.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


# `gh api .../contents/<path>` and `gh api repos/<o>/<r>/contents/<path>`.
# The bare `.../readme` endpoint is a separate path and is not matched here.
GH_API_CONTENTS = re.compile(r"\bgh\s+api\s+[^\n;&|]*?/contents/[^\s'\"]+")

# `glab api projects/<id>/repository/files/<path>`.
GLAB_API_FILES = re.compile(r"\bglab\s+api\s+[^\n;&|]*?/repository/files/[^\s'\"]+")

# `curl` / `wget` / `aria2c` / `fetch` against raw.githubusercontent.com,
# gitlab `-/raw/` blob URLs, or bitbucket `/raw/` blob URLs.
RAW_FETCH = re.compile(
    r"\b(?:curl|wget|aria2c|fetch)\b[^\n;&|]*?"
    r"(?:raw\.githubusercontent\.com|"
    r"gitlab\.com/[^\s'\"]+/-/raw/|"
    r"bitbucket\.org/[^\s'\"]+/raw/)"
)

# `gh repo view <owner>/<repo> <path>` reads file content. The bare form
# `gh repo view <owner>/<repo>` (no positional path) and flag-only forms
# (`--json`, `--web`, `--branch`) are metadata probes and stay allowed.
GH_REPO_VIEW_FILE = re.compile(r"\bgh\s+repo\s+view\s+\S+/\S+\s+(?!-)\S+")

from _lib.bypass import is_bypassed  # noqa: E402


def find_offender(command: str) -> tuple[str, str] | None:
    if GH_API_CONTENTS.search(command):
        return (
            "gh api .../contents/<path>",
            "Per-file content fetch through the GitHub API.",
        )
    if GLAB_API_FILES.search(command):
        return (
            "glab api .../repository/files/<path>",
            "Per-file content fetch through the GitLab API.",
        )
    if RAW_FETCH.search(command):
        return (
            "curl/wget against raw.githubusercontent.com (or equivalent)",
            "Per-file raw fetch from a remote repo.",
        )
    if GH_REPO_VIEW_FILE.search(command):
        return (
            "gh repo view <owner>/<repo> <path>",
            "Per-file content read through `gh repo view`.",
        )
    return None


def emit_block(label: str, why: str, command: str) -> None:
    reason = (
        f"BLOCKED: {label}.\n"
        f"{why}\n"
        f"Rule: ~/.claude/rules/repo-analysis.md.\n"
        f"\n"
        f"Fix: clone the repo to a temp dir and analyze locally.\n"
        f"  WORKDIR=$(mktemp -d -t repo-analysis-XXXXXX)\n"
        f'  git clone --depth=1 <repo-url> "$WORKDIR/repo"\n'
        f"  # then use Read, Grep, Glob against $WORKDIR/repo\n"
        f"\n"
        f"Carve-outs that stay allowed: `gh issue list`, `gh pr list`,\n"
        f"`gh pr diff <n>`, `gh search code`, single README probe via\n"
        f"`gh api repos/<o>/<r>/readme`, repo metadata `gh repo view <o>/<r>`.\n"
        f"\n"
        f"Private repo auth:\n"
        f"  git clone https://x-access-token:$(gh auth token --user <account>)@github.com/<owner>/<repo>.git\n"
        f"\n"
        f"Bypass (one-off, export in parent shell): REPO_FETCH_DISABLE=1"
    )
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
        hook="repo-fetch-blocker",
        decision="block",
        decision_class="block",
        reason=label[:200],
        tool="Bash",
        command_excerpt=command[:200],
    )
    sys.exit(2)


def main() -> int:
    if os.environ.get("REPO_FETCH_DISABLE") == "1":
        return 0
    if is_bypassed("repo-fetch-blocker"):
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

    offender = find_offender(command)
    if offender is None:
        return 0

    label, why = offender
    emit_block(label, why, command)
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())

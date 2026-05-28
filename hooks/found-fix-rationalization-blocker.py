#!/usr/bin/env python3
"""
found-fix-rationalization-blocker.py

PreToolUse hook that blocks the "found, did not fix" rationalization
pattern in artifacts other engineers will read: git commit messages,
PR/MR descriptions, release notes, issue bodies, code comments.

The trigger pattern: a verification surface (CI annotation, linter
warning, deprecation, security advisory) surfaces a problem; the
assistant declines to fix it and writes the decision into the commit
body, PR description, or release note. The dodge usually uses one
of a small set of phrases ("not introduced by this PR",
"pre-existing", "orthogonal to this task", "out of scope",
"leave for later"). When the phrase ends up in a published artifact,
the next reviewer treats it as established practice.

This hook does not catch the rationalization in the assistant's
in-conversation reply. That layer is handled by `rules/found-fix.md`
and the user's auto-memory. The hook handles the artifact layer.

Scans:
  - Write.content
  - Edit.new_string
  - MultiEdit.edits[].new_string
  - Bash.command  (only in scope when the command publishes text:
                   `git commit`, `git tag -m`, `gh pr/release/issue
                   create|edit|comment`, `glab mr/release create|update`)

Bypass:
  FOUND_FIX_RATIONALIZATION_DISABLE=1  (rare: when editing the rule
  file itself or writing a postmortem that legitimately discusses
  these phrases)

Source rule: ~/.claude/rules/found-fix.md
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


# Each pattern is paired with a short reason that becomes the
# blocker message. Patterns target the inaction-justification
# usage. Phrases that are fine in other contexts (history, design
# narrative) are accepted by limiting the trailing context to verbs
# that almost always indicate "we are not going to fix this".
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # "not introduced by this PR / MR / change / task / commit / work / patch"
    (
        re.compile(
            r"\bnot\s+introduced\s+by\s+(?:this|these|my|the)\s+"
            r"(?:pr|mr|change|task|commit|work|patch|fix|push)\b",
            re.IGNORECASE,
        ),
        "'not introduced by this <thing>' is a banned inaction rationalization",
    ),
    # "pre-existing, not mine" / "pre-existing concern, not in scope"
    (
        re.compile(
            r"\bpre[-\s]?existing\b[^.\n]*?\b"
            r"(?:not\s+(?:mine|introduced|in\s+scope|from\s+this|my\s+(?:task|change|pr|mr)))",
            re.IGNORECASE,
        ),
        "'pre-existing, not mine' is a banned inaction rationalization",
    ),
    # "orthogonal to this/the task / work / change / PR / MR"
    (
        re.compile(
            r"\borthogonal\s+to\s+(?:this|the)\s+"
            r"(?:task|work|change|pr|mr|commit|fix|push)\b",
            re.IGNORECASE,
        ),
        "'orthogonal to this <thing>' is a banned inaction rationalization",
    ),
    # "out of scope for/of this task / PR / MR / change / commit / work"
    (
        re.compile(
            r"\bout\s+of\s+scope\s+(?:for|of)\s+(?:this|the)\s+"
            r"(?:task|pr|mr|change|commit|work|fix|push)\b",
            re.IGNORECASE,
        ),
        "'out of scope of this <thing>' is a banned inaction rationalization",
    ),
    # "leave for later" / "leave for a future task" / "leave this for later"
    (
        re.compile(
            r"\bleave\s+(?:this\s+|it\s+)?for\s+(?:a\s+)?"
            r"(?:later|future|next|subsequent|follow[-\s]?up)\b",
            re.IGNORECASE,
        ),
        "'leave for later/future' defers a flagged issue; fix now",
    ),
    # "leave for a future task / PR / commit", "leave for the next PR"
    (
        re.compile(
            r"\bleave\s+for\s+(?:a|the)?\s*"
            r"(?:future|later|next|subsequent|follow[-\s]?up)\s+"
            r"(?:task|pr|mr|commit|change|work|fix)\b",
            re.IGNORECASE,
        ),
        "'leave for a future task/PR' defers a flagged issue; fix now",
    ),
    # "not blocking the run / build / pipeline / CI"
    (
        re.compile(
            r"\bnot\s+blocking\s+(?:the|this)\s+"
            r"(?:run|build|pipeline|ci|merge|deploy)\b",
            re.IGNORECASE,
        ),
        "'not blocking the run' treats annotations as non-blocking; they are blocking by rule",
    ),
    # "deprecation will be addressed later" / "annotation will be addressed in a future PR"
    (
        re.compile(
            r"\b(?:deprecation|annotation|warning|notice|alert)\s+"
            r"(?:will\s+be|to\s+be)\s+"
            r"(?:addressed|fixed|handled|resolved)\s+"
            r"(?:later|in\s+(?:a\s+)?(?:future|next|subsequent|follow[-\s]?up))",
            re.IGNORECASE,
        ),
        "Deferring a deprecation/annotation/warning is banned; fix in the same task",
    ),
]


# Paths whose content legitimately discusses these phrases (the rule
# file itself, the hook, the test file, the audit log, the memory).
SKIPPED_PATH_SEGMENTS = (
    "/.claude/rules/found-fix.md",
    "/rules/found-fix.md",
    "/hooks/found-fix-rationalization-blocker.py",
    "/tests/hooks/found-fix-rationalization-blocker/",
    "/memory/feedback_found_fix",
    "/CHANGELOG.md",
)


def is_skipped_path(path: str) -> bool:
    if not path:
        return False
    return any(seg in path for seg in SKIPPED_PATH_SEGMENTS)


# Bash commands that publish text to humans. Outside this set, the
# rationalization phrases are not in scope (e.g., `grep` for them in
# the codebase is fine).
PUBLISHING_BASH_PATTERNS = (
    re.compile(r"\bgit\s+commit\b"),
    re.compile(r"\bgit\s+tag\b.*-m\b"),
    re.compile(r"\bgit\s+notes\s+(?:add|append)\b"),
    re.compile(r"\bgh\s+pr\s+(?:create|edit|comment|review)\b"),
    re.compile(r"\bgh\s+release\s+(?:create|edit)\b"),
    re.compile(r"\bgh\s+issue\s+(?:create|edit|comment)\b"),
    re.compile(r"\bglab\s+mr\s+(?:create|update|note)\b"),
    re.compile(r"\bglab\s+release\s+create\b"),
    re.compile(r"\bglab\s+issue\s+(?:create|update|note)\b"),
)


def bash_command_publishes(command: str) -> bool:
    return any(pat.search(command) for pat in PUBLISHING_BASH_PATTERNS)


def collect_texts(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool in ("Write", "Edit", "MultiEdit") and is_skipped_path(fp):
        return out
    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append(("content", c))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append(("new_string", c))
    elif tool == "MultiEdit":
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((f"edits[{i}].new_string", c))
    elif tool == "Bash":
        c = tool_input.get("command", "")
        if isinstance(c, str) and bash_command_publishes(c):
            out.append(("command", c))
    return out


def find_violations(text: str) -> list[tuple[str, str, str]]:
    """Return a list of (matched_text, reason, snippet) tuples."""
    violations: list[tuple[str, str, str]] = []
    for pat, reason in PATTERNS:
        for m in pat.finditer(text):
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            snippet = text[start:end].replace("\n", " ")
            violations.append((m.group(0), reason, snippet))
    return violations


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("found-fix-rationalization-blocker"):
        _sys.exit(0)
    if os.environ.get("FOUND_FIX_RATIONALIZATION_DISABLE") == "1":
        _audit(
            hook="found-fix-rationalization-blocker",
            decision="bypass",
            bypass_env="FOUND_FIX_RATIONALIZATION_DISABLE",
        )
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    texts = collect_texts(tool, tool_input)
    if not texts:
        return 0

    findings: list[str] = []
    for field, text in texts:
        for match, reason, snippet in find_violations(text):
            findings.append(
                f"  - {match!r} ({reason})\n    in {field}: ...{snippet}..."
            )

    if not findings:
        return 0

    print(
        "Blocked: 'found, did not fix' rationalization detected in artifact.\n"
        "Rule: ~/.claude/rules/found-fix.md.\n"
        "A problem surfaced by a verification surface is in scope for the\n"
        "current task regardless of when it was introduced. Fix it, then\n"
        "rewrite the artifact without the inaction language.\n\n"
        + "\n".join(findings)
        + "\n\nFix: address the underlying issue, then write the commit/PR\n"
        "body in terms of what changed and why. Do not justify inaction\n"
        "on a flagged issue.\n\n"
        "Bypass (rare; when writing about the rule itself or a postmortem\n"
        "that legitimately discusses these phrases):\n"
        "  export FOUND_FIX_RATIONALIZATION_DISABLE=1",
        file=sys.stderr,
    )
    _audit(
        hook="found-fix-rationalization-blocker",
        decision="block",
        tool=tool,
        reason="found-fix rationalization detected",
        command_excerpt=" | ".join(f[:120] for f in findings)[:240]
        if findings
        else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

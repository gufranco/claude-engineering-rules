#!/usr/bin/env python3
"""Block edits that introduce NEW bare file mentions in markdown.

The hook is diff-aware. It does not flag pre-existing bare references in
the file being edited so legacy markdown can be edited without triggering.
Only new bare references introduced by the change are blocked.

Rule source: ``rules/markdown-links.md``.

Bypass: set ``MARKDOWN_LINKS_DISABLE=1`` in the environment.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path("/Users/gufranco/.claude").resolve()
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


try:
    from markdown_link_detector import (  # type: ignore
        Finding,
        detect_findings,
        is_advisory_file,
        tracked_paths,
    )
except ImportError:  # pragma: no cover
    sys.exit(0)


MARKDOWN_EXTENSIONS = (".md", ".mdx")


def is_markdown_path(path: str) -> bool:
    return any(path.lower().endswith(ext) for ext in MARKDOWN_EXTENSIONS)


def relative_to_repo(path: str) -> str | None:
    try:
        p = Path(path).resolve()
        return str(p.relative_to(REPO_ROOT))
    except (ValueError, OSError):
        return None


def findings_signature(findings: list[Finding]) -> set[tuple[str, int, str]]:
    """Return a comparable set of (line-anchor, column, token) for diffing.

    Line numbers can shift between the pre-edit and post-edit content. To
    minimize false positives, we use (line content, token) as the anchor,
    keyed off the token plus the surrounding context, rather than line number
    alone.
    """
    return {(f.token, f.column, f.line) for f in findings}


def derive_post_text(tool: str, tool_input: dict, pre_text: str) -> str:
    """Apply the Write/Edit/MultiEdit operation to produce the post-edit text."""
    if tool == "Write":
        return tool_input.get("content", "")
    if tool == "Edit":
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        replace_all = tool_input.get("replace_all", False)
        if not old:
            return pre_text
        if replace_all:
            return pre_text.replace(old, new)
        return pre_text.replace(old, new, 1)
    if tool == "MultiEdit":
        text = pre_text
        for edit in tool_input.get("edits", []) or []:
            old = edit.get("old_string", "")
            new = edit.get("new_string", "")
            replace_all = edit.get("replace_all", False)
            if not old:
                continue
            if replace_all:
                text = text.replace(old, new)
            else:
                text = text.replace(old, new, 1)
        return text
    return pre_text


import sys as _sys, os as _os
_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.profile import should_run  # noqa: E402
except ImportError:
    def should_run(_id: str) -> bool:
        return True


def main() -> None:
    if not should_run("markdown-link-discipline"):
        _sys.exit(0)
    if os.environ.get("MARKDOWN_LINKS_DISABLE") == "1":
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool = data.get("tool_name", "")
    if tool not in {"Write", "Edit", "MultiEdit"}:
        sys.exit(0)

    tool_input = data.get("tool_input", data.get("input", {}))
    file_path = tool_input.get("file_path", "")
    if not file_path or not is_markdown_path(file_path):
        sys.exit(0)

    rel = relative_to_repo(file_path)
    if rel is None:
        sys.exit(0)

    if is_advisory_file(rel):
        sys.exit(0)

    # Read pre-edit text from disk for Edit/MultiEdit. For Write, the pre
    # state is the empty file when the path does not yet exist.
    disk_path = Path(file_path)
    pre_text = ""
    if disk_path.exists():
        try:
            pre_text = disk_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            sys.exit(0)

    post_text = derive_post_text(tool, tool_input, pre_text)

    tracked = tracked_paths(REPO_ROOT)
    pre_findings = (
        detect_findings(pre_text, rel, REPO_ROOT, tracked=tracked) if pre_text else []
    )
    post_findings = detect_findings(post_text, rel, REPO_ROOT, tracked=tracked)

    pre_tokens = {f.token for f in pre_findings}
    new_findings = [f for f in post_findings if f.token not in pre_tokens]

    if not new_findings:
        sys.exit(0)

    print(
        "BLOCKED: markdown link discipline.\n"
        f"The change to {rel} introduces {len(new_findings)} new bare file "
        "reference(s) whose path resolves to an existing repo file.\n"
        "Wrap each reference as `[`<name>`](<path>)` or `[<name>](<path>)`.\n"
        "Rule: rules/markdown-links.md\n"
        "Bypass: set MARKDOWN_LINKS_DISABLE=1 in the environment.\n"
        "Findings:",
        file=sys.stderr,
    )
    for f in new_findings[:10]:
        print(f"  {f.render()}", file=sys.stderr)
    if len(new_findings) > 10:
        print(f"  ... and {len(new_findings) - 10} more", file=sys.stderr)

    _audit(
        hook="markdown-link-discipline",
        decision="block",
        tool=tool,
        reason="new bare file references introduced",
        file=rel,
        new_count=len(new_findings),
    )
    sys.exit(2)


if __name__ == "__main__":
    main()

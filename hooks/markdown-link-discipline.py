#!/usr/bin/env python3
from __future__ import annotations

import functools
import os
import sys
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.audit_log import record as _audit  # noqa: E402


from _lib.markdown_link_detector import (  # noqa: E402
    Finding,
    detect_findings,
    is_advisory_file,
    tracked_paths,
)


MARKDOWN_EXTENSIONS = (".md", ".mdx")

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402


def is_markdown_path(path: str) -> bool:
    return any(path.lower().endswith(ext) for ext in MARKDOWN_EXTENSIONS)


def find_repo_root(path: str) -> Path | None:
    try:
        resolved = Path(path).resolve()
    except OSError:
        return None
    for candidate in resolved.parents:
        if (candidate / ".git").exists():
            return candidate
    return None


def relative_to_repo(path: str, repo_root: Path) -> str:
    return str(Path(path).resolve().relative_to(repo_root))


def _text(fields: Mapping[str, object], key: str) -> str:
    value = fields.get(key, "")
    return value if isinstance(value, str) else ""


def _apply_edit(text: str, edit: Mapping[str, object]) -> str:
    old = _text(edit, "old_string")
    if not old:
        return text
    new = _text(edit, "new_string")
    if edit.get("replace_all", False):
        return text.replace(old, new)
    return text.replace(old, new, 1)


def _edits(tool_input: Mapping[str, object]) -> list[Mapping[str, object]]:
    edits = tool_input.get("edits") or []
    if not isinstance(edits, list):
        return []
    return [edit for edit in edits if isinstance(edit, dict)]


def derive_post_text(tool: str, tool_input: Mapping[str, object], pre_text: str) -> str:
    if tool == "Write":
        return _text(tool_input, "content")
    if tool == "Edit":
        return _apply_edit(pre_text, tool_input)
    if tool == "MultiEdit":
        return functools.reduce(_apply_edit, _edits(tool_input), pre_text)
    return pre_text


from _lib.hook_profile import should_run  # noqa: E402


def _disabled() -> bool:
    return (
        not should_run("markdown-link-discipline")
        or os.environ.get("MARKDOWN_LINKS_DISABLE") == "1"
        or is_bypassed("markdown-link-discipline")
    )


def _read_pre_text(file_path: str) -> str | None:
    disk_path = Path(file_path)
    if not disk_path.exists():
        return ""
    try:
        return disk_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _new_findings(
    tool: str,
    tool_input: dict[str, object],
    pre_text: str,
    rel: str,
    repo_root: Path,
) -> list[Finding]:
    post_text = derive_post_text(tool, tool_input, pre_text)
    tracked = tracked_paths(repo_root)
    pre_findings = (
        detect_findings(pre_text, rel, repo_root, tracked=tracked) if pre_text else []
    )
    post_findings = detect_findings(post_text, rel, repo_root, tracked=tracked)
    pre_tokens = {f.token for f in pre_findings}
    return [f for f in post_findings if f.token not in pre_tokens]


def _report(tool: str, rel: str, new_findings: list[Finding]) -> int:
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
    return 2


def _markdown_target(
    data: dict[str, object],
) -> tuple[str, dict[str, object], str] | None:
    tool = data.get("tool_name", "")
    if tool not in {"Write", "Edit", "MultiEdit"} or not isinstance(tool, str):
        return None
    tool_input = tool_input_of(data)
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return None
    if not is_markdown_path(file_path):
        return None
    return tool, tool_input, file_path


def _run() -> int:
    if _disabled():
        return 0
    target = _markdown_target(read_hook_payload("markdown-link-discipline"))
    if target is None:
        return 0
    tool, tool_input, file_path = target
    repo_root = find_repo_root(file_path)
    if repo_root is None:
        return 0
    rel = relative_to_repo(file_path, repo_root)
    if is_advisory_file(rel):
        return 0
    pre_text = _read_pre_text(file_path)
    if pre_text is None:
        return 0
    new_findings = _new_findings(tool, tool_input, pre_text, rel, repo_root)
    if not new_findings:
        return 0
    return _report(tool, rel, new_findings)


def main() -> None:
    sys.exit(_run())


if __name__ == "__main__":
    main()

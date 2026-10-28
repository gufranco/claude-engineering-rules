#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
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
from _lib.edit_resolution import resolved_change  # noqa: E402


def is_markdown_path(path: str) -> bool:
    return any(path.lower().endswith(ext) for ext in MARKDOWN_EXTENSIONS)


def find_repo_root(path: str) -> Path | None:
    for candidate in Path(path).resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    return None


def relative_to_repo(path: str, repo_root: Path) -> str:
    return str(Path(path).resolve().relative_to(repo_root))


from _lib.hook_profile import should_run  # noqa: E402


def _disabled() -> bool:
    return (
        not should_run("markdown-link-discipline")
        or os.environ.get("MARKDOWN_LINKS_DISABLE") == "1"
        or is_bypassed("markdown-link-discipline")
    )


def _new_findings(
    pre_text: str, post_text: str, rel: str, repo_root: Path
) -> list[Finding]:
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
    tool = str(data.get("tool_name", ""))
    tool_input = tool_input_of(data)
    file_path = str(tool_input.get("file_path") or "")
    if tool not in {"Write", "Edit", "MultiEdit"} or not is_markdown_path(file_path):
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
    change = resolved_change(tool, tool_input)
    if change is None:
        return 0
    new_findings = _new_findings(change.before, change.after, rel, repo_root)
    if not new_findings:
        return 0
    return _report(tool, rel, new_findings)


def main() -> None:
    sys.exit(_run())


if __name__ == "__main__":
    main()

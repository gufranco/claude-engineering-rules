#!/usr/bin/env python3
"""comment-blocker

PreToolUse hook that blocks ANY newly added source-code comment.
Rule source: ~/.claude/rules/code-style.md "Comments Policy" (code must be
self-explanatory; comments are not permitted). There is no code-level
suppression: a comment is always blocked. The single exception is the exact
Arrange-Act-Assert markers inside test files, mandated by
~/.claude/rules/testing.md.

What is blocked (per language family, string-literal aware):
  - C family (`//` line, `/* ... */` block): ts, tsx, js, jsx, mjs, cjs,
    java, c, cpp, cc, cxx, h, hpp, hh, cs, go, rs, swift, scala, kt, kts,
    m, mm, php, dart. JSX `{/* ... */}` is caught by the block delimiters.
  - Hash family (`#` line): py, rb, sh, bash, zsh. A first-line `#!` shebang
    is never flagged.

The scanner masks string and template literals before looking for comment
tokens, so `https://` inside a string, a JS private field `this.#x`, and a
`#` inside a Python docstring do not trigger a false positive.

Test files (`*.test.*`, `*.spec.*`, `test_*.py`, `*_test.go`,
`**/__tests__/**`, `**/tests/**`, `**/e2e/**`) are scanned, not skipped:
every comment is blocked EXCEPT a standalone `// Arrange`, `// Act`,
`// Assert`, or a `/`-joined combination of those.

Out of scope (not project source we author):
  - Planning artifacts: **/specs/**, **/docs/adr/**, **/docs/plan*/**
  - Templates: **/templates/**
  - The ~/.claude/ tree itself, node_modules, vendor, dist, build, .git.
  - Any extension without a known comment syntax (markdown, json, `.ts.tmpl`).

Bypass (operator kill switch, not a per-comment escape hatch):
  COMMENT_BLOCKER_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from _lib.audit_log import record as _audit
except Exception:  # pragma: no cover

    def _audit(**_fields: object) -> None:  # type: ignore[misc]
        return None


C_FAMILY_EXTS: tuple[str, ...] = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".java",
    ".c",
    ".cpp",
    ".cc",
    ".cxx",
    ".h",
    ".hpp",
    ".hh",
    ".cs",
    ".go",
    ".rs",
    ".swift",
    ".scala",
    ".kt",
    ".kts",
    ".m",
    ".mm",
    ".php",
    ".dart",
)

HASH_FAMILY_EXTS: tuple[str, ...] = (
    ".py",
    ".rb",
    ".sh",
    ".bash",
    ".zsh",
)

C_FAMILY: dict[str, Any] = {
    "block": ("/*", "*/"),
    "line": ("//",),
    "strings": ('"', "'", "`"),
}

HASH_FAMILY: dict[str, Any] = {
    "block": None,
    "line": ("#",),
    "strings": ('"""', "'''", '"', "'"),
}

SKIP_SEGMENTS: tuple[str, ...] = (
    "/specs/",
    "/docs/adr/",
    "/docs/plan/",
    "/docs/plans/",
    "/docs/planning/",
    "/templates/",
    "/template/",
    "/.claude/",
    "/node_modules/",
    "/vendor/",
    "/.git/",
    "/dist/",
    "/build/",
)

TEST_SEGMENTS: tuple[str, ...] = (
    "/__tests__/",
    "/__test__/",
    "/tests/",
    "/test/",
    "/e2e/",
)

TEST_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".test.mjs",
    ".test.cjs",
    ".test.py",
    ".test.rs",
    ".test.go",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    ".spec.mjs",
    ".spec.cjs",
    ".spec.py",
)

AAA_MARKER = re.compile(
    r"^(?://|#)\s*(?:Arrange|Act|Assert)(?:\s*/\s*(?:Arrange|Act|Assert))*$"
)

from _lib.bypass import is_bypassed  # noqa: E402


def resolve_family(path: str) -> "dict[str, Any] | None":
    """Return the comment family for a scannable source file, else None.

    None means the file is out of scope: no path, a planning or vendor path,
    or an extension without a known comment syntax.
    """
    if not path:
        return None
    p = path.lower()
    if any(seg in p for seg in SKIP_SEGMENTS):
        return None
    if p.endswith(C_FAMILY_EXTS):
        return C_FAMILY
    if p.endswith(HASH_FAMILY_EXTS):
        return HASH_FAMILY
    return None


def is_test_file(path: str) -> bool:
    """True for files where the AAA markers are the one permitted comment."""
    p = path.lower()
    base = p.rsplit("/", 1)[-1]
    if (
        base.startswith("test_")
        or base.endswith("_test.py")
        or base.endswith("_test.go")
    ):
        return True
    if any(p.endswith(suf) for suf in TEST_SUFFIXES):
        return True
    return any(seg in p for seg in TEST_SEGMENTS)


def collect(tool: str, tool_input: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return (file_path, field_name, text) tuples for Write/Edit/MultiEdit."""
    out: list[tuple[str, str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((fp, "content", c))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((fp, "new_string", c))
    elif tool == "MultiEdit":
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((fp, f"edits[{i}].new_string", c))
    return out


def scan_comment_lines(text: str, family: dict[str, Any]) -> set[int]:
    """Return 0-based indices of lines that begin or continue a comment.

    A string-literal aware char scanner. Comment tokens inside strings or
    template literals are ignored. A first-line `#!` shebang is ignored.
    """
    block = family["block"]
    line_tokens = family["line"]
    strings = family["strings"]

    hits: set[int] = set()
    i = 0
    n = len(text)
    line_idx = 0
    state = "normal"
    string_delim = ""

    if text.startswith("#!") and "#" in line_tokens:
        state = "line_comment"
        i = 2

    while i < n:
        ch = text[i]
        if ch == "\n":
            line_idx += 1
            if state == "line_comment":
                state = "normal"
            i += 1
            continue

        if state == "normal":
            if block and text.startswith(block[0], i):
                hits.add(line_idx)
                state = "block_comment"
                i += len(block[0])
                continue
            matched_line = next(
                (lt for lt in line_tokens if text.startswith(lt, i)), None
            )
            if matched_line:
                hits.add(line_idx)
                state = "line_comment"
                i += len(matched_line)
                continue
            matched_string = next((d for d in strings if text.startswith(d, i)), None)
            if matched_string:
                state = "string"
                string_delim = matched_string
                i += len(matched_string)
                continue
            i += 1
            continue

        if state == "string":
            if ch == "\\":
                i += 2
                continue
            if text.startswith(string_delim, i):
                state = "normal"
                i += len(string_delim)
                continue
            i += 1
            continue

        if state == "block_comment":
            hits.add(line_idx)
            if block and text.startswith(block[1], i):
                state = "normal"
                i += len(block[1])
                continue
            i += 1
            continue

        i += 1

    return hits


def find(text: str, family: dict[str, Any], allow_aaa: bool) -> list[str]:
    """Return comment snippets per line. Only the AAA test markers are exempt."""
    comment_lines = scan_comment_lines(text, family)
    if not comment_lines:
        return []

    lines = text.splitlines()
    hits: list[str] = []
    for idx in sorted(comment_lines):
        if idx >= len(lines):
            continue
        stripped = lines[idx].strip()
        if allow_aaa and AAA_MARKER.match(stripped):
            continue
        snippet = stripped if len(stripped) <= 60 else stripped[:57] + "..."
        hits.append(f"L{idx + 1}: {snippet}")
    return hits


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(hook_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("comment-blocker"):
        _sys.exit(0)
    if os.environ.get("COMMENT_BLOCKER_DISABLE") == "1":
        _audit(
            hook="comment-blocker",
            decision="bypass",
            bypass_env="COMMENT_BLOCKER_DISABLE",
        )
        return 0
    if is_bypassed("comment-blocker"):
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    findings: list[str] = []
    for path, field, text in items:
        family = resolve_family(path)
        if family is None:
            continue
        hits = find(text, family, allow_aaa=is_test_file(path))
        if hits:
            findings.append(f"  - {field} ({path}):\n      " + "\n      ".join(hits))

    if not findings:
        return 0

    print(
        "Blocked: comment added to source code. "
        'Rule: ~/.claude/rules/code-style.md "Comments Policy" '
        "(code must be self-explanatory; comments are not permitted).\n"
        + "\n".join(findings)
        + "\n\nThere is no per-comment suppression. Fix the code instead:\n"
        "  1. Delete the comment. If code felt like it needed explaining, that is\n"
        "     the signal to improve the code: rename the symbol, extract a\n"
        "     well-named function, or split the expression until it reads clearly.\n"
        "  2. For a public-API contract, express intent in types, not prose.\n"
        "  3. In test files, the only permitted comments are `// Arrange`, `// Act`,\n"
        "     and `// Assert` (or a `/`-joined combination), with no description.",
        file=sys.stderr,
    )
    _audit(
        hook="comment-blocker",
        decision="block",
        tool=tool,
        reason="comment added to source",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""comment-blocker

PreToolUse hook that blocks ANY newly added source-code comment written as
prose. Rule source: ~/.claude/rules/code-style.md "Comments Policy" (code must
be self-explanatory; comments are not permitted). There is no code-level
suppression: prose is blocked in every scanned file, test files included.

The one class that passes is a tool directive: a comment a tool parses and
acts on, where the comment syntax is the only channel the tool offers.
`// eslint-disable-next-line`, `// @ts-expect-error`, `//go:build`,
`# noqa: E501`, `# type: ignore`, `# pragma: no cover`,
`# shellcheck disable=SC2086`, `// prettier-ignore`. These are machine input,
not explanation, so the drift argument behind the rule does not apply: when
the directive goes stale the tool reports it. A directive is matched at the
start of the comment body, so a trailing justification stays allowed
(`// eslint-disable-next-line no-console -- CLI entry point`), while prose
that merely mentions a tool name is still blocked.

What is blocked (per language family, string-literal aware):
  - C family (`//` line, `/* ... */` block): ts, tsx, js, jsx, mjs, cjs,
    java, c, cpp, cc, cxx, h, hpp, hh, cs, go, rs, swift, scala, kt, kts,
    m, mm, php, dart. JSX `{/* ... */}` is caught by the block delimiters.
  - Python family (line token `#`): py, pyi, pyw. Triple quotes span lines;
    a single-quoted string ends at the newline, which is what the language
    allows and what keeps one stray quote from masking the rest of a file.
  - Shell and Ruby family (line token `#`): rb, sh, bash, zsh. Every quote
    spans lines there, so no newline recovery applies.
  A first-line shebang is never flagged in either hash family.

The scanner masks string and template literals before looking for comment
tokens, so a URL inside a string, a JS private field, and a hash inside a
Python docstring do not trigger a false positive.

An Edit or MultiEdit payload carries a fragment, and a fragment can open or
close a string it does not contain both ends of. Scanning it alone reads the
tail of a docstring as the start of one, so every comment below is swallowed
as string content, and the prose above it is read as comments. The hook
therefore applies the edit to the file on disk and scans the resulting
document, where every delimiter is paired, then reports only the comments
that document holds and the original did not. When the file cannot be read
or old_string does not match, the payload is scanned on its own, and an edit
whose old_string does not match was going to fail anyway.

Test files (`*.test.*`, `*.spec.*`, `test_*.py`, `*_test.go`,
`**/__tests__/**`, `**/tests/**`, `**/e2e/**`) are scanned like any other
source file. A test body carries zero comments; structure it with the test
name, blank lines, and named helpers instead.

Out of scope (not project source we author):
  - Planning artifacts: **/specs/**, **/docs/adr/**, **/docs/plan*/**
  - Templates: **/templates/**
  - node_modules, vendor, dist, build, .git.
  - Any extension without a known comment syntax (markdown, json, `.ts.tmpl`).

The ~/.claude/ tree is in scope. It is source we author and publish, so the
rule that governs every other repository governs this one. Python docstrings
are string expressions rather than comments and stay allowed; rationale that
would have been a comment belongs in the module or function docstring.

Bypass (operator kill switch, not a per-comment escape hatch):
  COMMENT_BLOCKER_DISABLE=1

To allow a directive from a tool not yet covered, add it to TOOL_DIRECTIVE.
Never widen that pattern to admit prose.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
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

PYTHON_FAMILY_EXTS: tuple[str, ...] = (
    ".py",
    ".pyi",
    ".pyw",
)

HASH_FAMILY_EXTS: tuple[str, ...] = (
    ".rb",
    ".sh",
    ".bash",
    ".zsh",
)

C_FAMILY: dict[str, Any] = {
    "block": ("/*", "*/"),
    "line": ("//",),
    "strings": ('"', "'", "`"),
    "line_terminated": (),
}

PYTHON_FAMILY: dict[str, Any] = {
    "block": None,
    "line": ("#",),
    "strings": ('"""', "'''", '"', "'"),
    "line_terminated": ('"', "'"),
}

HASH_FAMILY: dict[str, Any] = {
    "block": None,
    "line": ("#",),
    "strings": ('"""', "'''", '"', "'"),
    "line_terminated": (),
}

MAX_RESOLVE_BYTES = 512 * 1024

SKIP_SEGMENTS: tuple[str, ...] = (
    "/specs/",
    "/docs/adr/",
    "/docs/plan/",
    "/docs/plans/",
    "/docs/planning/",
    "/templates/",
    "/template/",
    "/node_modules/",
    "/vendor/",
    "/.git/",
    "/dist/",
    "/build/",
)

TOOL_DIRECTIVE = re.compile(
    r"""^(?:
        eslint- (?: disable | enable ) \b
      | eslint-env \b
      | eslint \s+ [\w@/-]+ \s* :
      | oxlint- (?: disable | enable ) \b
      | biome-ignore \b
      | prettier-ignore \b
      | stylelint- (?: disable | enable ) \b
      | tslint:
      | jshint \s
      | jslint \s
      | @ts- (?: expect-error | ignore | nocheck | check ) \b
      | @jsx \w* \b
      | @formatter: \s* (?: off | on ) \b
      | / \s* <reference \b
      | \#\s* source (?: MappingURL | URL ) =
      | \#__ (?: PURE | NO_SIDE_EFFECTS ) __
      | webpack (?: ChunkName | Ignore | Mode | Prefetch | Preload ) \b
      | (?: @ )? vite-ignore \b
      | istanbul \s+ ignore \b
      | [cv]8 \s+ ignore \b
      | go: (?: build | generate | embed | linkname | noinline | nosplit ) \b
      | \+build \b
      | nolint \b
      | swiftlint: (?: disable | enable ) \b
      | ktlint- (?: disable | enable ) \b
      | detekt:
      | NOPMD \b
      | NOSONAR \b
      | CHECKSTYLE: (?: OFF | ON ) \b
      | noinspection \b
      | ReSharper \s+ (?: disable | restore ) \b
      | ignore (?: _for_file )? : \s* \S
      | noqa \s* (?: : \s* \S+ )? \s* $
      | nosec \b (?: \s+ B\d+ )* \s* $
      | type: \s* ignore \b
      | pragma: \s* \S
      | mypy:
      | pyright:
      | ruff:
      | flake8:
      | pylint: \s* (?: disable | enable | skip-file ) \b
      | fmt: \s* (?: off | on | skip ) \b
      | yapf: \s* (?: disable | enable ) \b
      | isort:
      | coverage: \s* ignore \b
      | shellcheck \s+ (?: disable | shell | source | source-path | external-sources ) \b
      | shfmt:
      | -\*- \s* coding: \s* \S
      | SAFETY:
      | SPDX- [\w-]+ :
      | REUSE-Ignore (?: Start | End ) \b
      | cSpell:
      | spell-checker:
      | codespell:
    )""",
    re.VERBOSE | re.IGNORECASE,
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
    if p.endswith(PYTHON_FAMILY_EXTS):
        return PYTHON_FAMILY
    if p.endswith(HASH_FAMILY_EXTS):
        return HASH_FAMILY
    return None


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


def scan_comments(text: str, family: dict[str, Any]) -> dict[int, "str | None"]:
    """Map 0-based line index to the body of the comment opened on that line.

    A line that only continues a block comment maps to None, so it can never
    qualify as a tool directive. A string-literal aware char scanner: comment
    tokens inside strings or template literals are ignored, and a first-line
    shebang is ignored. A delimiter listed in `line_terminated` closes at the
    newline, matching a language that forbids a raw newline inside it.
    """
    block = family["block"]
    line_tokens = family["line"]
    strings = family["strings"]
    line_terminated = family.get("line_terminated", ())

    hits: dict[int, str | None] = {}

    def open_comment(start: int, token: str) -> None:
        line_end = text.find("\n", start)
        body = text[start + len(token) : line_end if line_end != -1 else len(text)]
        if block:
            closed = body.find(block[1])
            if closed != -1:
                body = body[:closed]
        hits.setdefault(line_idx, body.strip().lstrip("*").strip())

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
            elif state == "string" and string_delim in line_terminated:
                state = "normal"
            i += 1
            continue

        if state == "normal":
            if block and text.startswith(block[0], i):
                open_comment(i, block[0])
                state = "block_comment"
                i += len(block[0])
                continue
            matched_line = next(
                (lt for lt in line_tokens if text.startswith(lt, i)), None
            )
            if matched_line:
                open_comment(i, matched_line)
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
                if text[i + 1 : i + 2] == "\n":
                    line_idx += 1
                i += 2
                continue
            if text.startswith(string_delim, i):
                state = "normal"
                i += len(string_delim)
                continue
            i += 1
            continue

        if state == "block_comment":
            hits.setdefault(line_idx, None)
            if block and text.startswith(block[1], i):
                state = "normal"
                i += len(block[1])
                continue
            i += 1
            continue

        i += 1

    return hits


def find_pairs(text: str, family: dict[str, Any]) -> list[tuple[int, str]]:
    """Return (0-based line index, whole stripped line) per prose comment.

    Tool directives are exempt. The whole line is carried rather than the
    comment body so a trailing comment keeps the code that precedes it, which
    is what makes two occurrences of the same comment text distinguishable.
    """
    comments = scan_comments(text, family)
    if not comments:
        return []

    lines = text.splitlines()
    pairs: list[tuple[int, str]] = []
    for idx in sorted(comments):
        if idx >= len(lines):
            continue
        body = comments[idx]
        if body and TOOL_DIRECTIVE.match(body):
            continue
        pairs.append((idx, lines[idx].strip()))
    return pairs


def format_hits(pairs: list[tuple[int, str]]) -> list[str]:
    """Render (line index, line) pairs as the `L<n>: <snippet>` report lines."""
    return [
        f"L{idx + 1}: {line if len(line) <= 60 else line[:57] + '...'}"
        for idx, line in pairs
    ]


def find(text: str, family: dict[str, Any]) -> list[str]:
    """Return prose-comment snippets per line. Tool directives are exempt."""
    return format_hits(find_pairs(text, family))


def added_pairs(
    before: str, after: str, family: dict[str, Any]
) -> list[tuple[int, str]]:
    """Return the comments `after` holds that `before` did not.

    Matching is by line text against a count of the same text in `before`, so
    a comment that only moved is not reported and a genuine second copy of an
    existing comment line still is.
    """
    remaining = Counter(line for _, line in find_pairs(before, family))
    added: list[tuple[int, str]] = []
    for idx, line in find_pairs(after, family):
        if remaining.get(line):
            remaining[line] -= 1
            continue
        added.append((idx, line))
    return added


def read_source(path: str) -> "str | None":
    """Return the file's current text, or None when it cannot be read.

    A file past MAX_RESOLVE_BYTES also reads as None: resolving the edit costs
    two scans of the whole document, and past that ceiling the latency is worth
    more than what the resolution buys on a file that large.
    """
    try:
        if os.path.getsize(path) > MAX_RESOLVE_BYTES:
            return None
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None
    except UnicodeDecodeError:
        return None


def apply_edit(text: str, edit: dict[str, Any]) -> "str | None":
    """Return `text` with one edit applied, or None when it does not apply."""
    old = edit.get("old_string")
    new = edit.get("new_string")
    if not isinstance(old, str) or not isinstance(new, str):
        return None
    if not old or old not in text:
        return None
    return (
        text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    )


def apply_edits(text: str, tool: str, tool_input: dict[str, Any]) -> "str | None":
    """Return the file text an Edit or MultiEdit payload would produce.

    None means the payload cannot be resolved against the file on disk, which
    also means the tool call itself is about to fail on the same mismatch.
    """
    if tool == "Edit":
        return apply_edit(text, tool_input)
    if tool == "MultiEdit":
        edits = tool_input.get("edits") or []
        if not edits:
            return None
        for edit in edits:
            if not isinstance(edit, dict):
                return None
            updated = apply_edit(text, edit)
            if updated is None:
                return None
            text = updated
        return text
    return None


def resolved_findings(tool: str, tool_input: dict[str, Any]) -> "list[str] | None":
    """Return report lines from the document the edit produces, or None.

    None means the edit could not be resolved against the file on disk and the
    caller falls back to scanning the payload fragment on its own.
    """
    if tool not in ("Edit", "MultiEdit"):
        return None
    path = tool_input.get("file_path", "") or ""
    family = resolve_family(path)
    if family is None:
        return None
    before = read_source(path)
    if before is None:
        return None
    after = apply_edits(before, tool, tool_input)
    if after is None:
        return None
    hits = format_hits(added_pairs(before, after, family))
    if not hits:
        return []
    return [
        f"  - {path} (line numbers in the file this edit produces):\n      "
        + "\n      ".join(hits)
    ]


def fragment_findings(tool: str, tool_input: dict[str, Any]) -> list[str]:
    """Return report lines from the payload text alone."""
    findings: list[str] = []
    for path, field, text in collect(tool, tool_input):
        family = resolve_family(path)
        if family is None:
            continue
        hits = find(text, family)
        if hits:
            findings.append(f"  - {field} ({path}):\n      " + "\n      ".join(hits))
    return findings


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

    findings = resolved_findings(tool, tool_input)
    if findings is None:
        findings = fragment_findings(tool, tool_input)
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
        "  3. Test files have no carve-out. Structure a test with its name, blank\n"
        "     lines between setup, call, and assertions, and named helpers.\n"
        "  4. Tool directives are the one exempt class and are already allowed:\n"
        "     `// eslint-disable-next-line`, `// @ts-expect-error`, `//go:build`,\n"
        "     `# noqa`, `# type: ignore`, `# shellcheck disable=SC2086`. If a real\n"
        "     directive was flagged, it is missing from the allowlist in\n"
        "     ~/.claude/hooks/comment-blocker.py.",
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

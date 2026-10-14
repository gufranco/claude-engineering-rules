from __future__ import annotations

import re
from collections.abc import Iterator, Sequence

from .guard_runner import Edit, Finding
from .polyglot_mutation_common import CommentStyle, mask_source, suppressed_filter

RUBY_MAGIC_COMMENT = re.compile(r"^#\s*frozen_string_literal:\s*true\b")
RUBY_MAGIC_WINDOW = 3
RUBY_EXEMPT_SEGMENTS = ("/db/schema.rb", "/db/structure.rb", "/Formula/", "/Casks/")
RUBY_MUTABLE_CONSTANT = re.compile(
    r"^\s*(?P<name>[A-Z][A-Z0-9_]*)\s*=\s*(?P<open>\[|\{|%[wiWI][\[({<])"
)
CLOSERS = {"[": "]", "{": "}", "(": ")", "<": ">"}

LUA_LOCAL = re.compile(r"\blocal\s+(?:function\s+)?(?P<names>[A-Za-z_][\w\s,]*)")
LUA_FUNCTION_PARAMS = re.compile(r"\bfunction\b[^(]*\((?P<params>[^)]*)\)")
LUA_FOR_VARS = re.compile(r"\bfor\s+(?P<names>[A-Za-z_][\w\s,]*?)\s*(?:=|\bin\b)")
LUA_ASSIGNMENT = re.compile(r"^\s*(?P<name>[A-Za-z_]\w*)\s*=(?!=)")
LUA_GLOBAL_FUNCTION = re.compile(r"^\s*function\s+(?P<name>[A-Za-z_]\w*)\s*\(")
LUA_KEYWORDS = frozenset(
    {
        "local",
        "function",
        "for",
        "if",
        "while",
        "return",
        "end",
        "then",
        "do",
        "else",
        "elseif",
        "until",
        "repeat",
    }
)


def _ruby_missing_magic(edit: Edit) -> Iterator[Finding]:
    head = edit.text.splitlines()[:RUBY_MAGIC_WINDOW]
    if edit.full_file and not any(RUBY_MAGIC_COMMENT.match(line) for line in head):
        yield Finding(
            line=1,
            message="missing `# frozen_string_literal: true`; string literals in this file stay mutable",
        )


def _closing_line(masked: Sequence[str], start: int, opener: str) -> int:
    closer = CLOSERS[opener[-1]]
    depth = 0
    for index in range(start, len(masked)):
        depth += masked[index].count(opener[-1]) - masked[index].count(closer)
        if depth <= 0:
            return index
    return len(masked) - 1


def _ruby_constant_hits(masked: Sequence[str]) -> Iterator[Finding]:
    for index, line in enumerate(masked):
        match = RUBY_MUTABLE_CONSTANT.match(line)
        if match is None:
            continue
        close = _closing_line(masked, index, match.group("open"))
        if ".freeze" not in masked[close]:
            yield Finding(
                line=index + 1,
                message=f"constant `{match.group('name')}` holds a mutable collection; append `.freeze`",
            )


def find_ruby(edit: Edit) -> tuple[Finding, ...]:
    if any(segment in edit.path for segment in RUBY_EXEMPT_SEGMENTS):
        return ()
    masked = mask_source(edit.text, CommentStyle.HASH)
    hits = [*_ruby_missing_magic(edit), *_ruby_constant_hits(masked)]
    return suppressed_filter(edit.text, hits)


def _split_names(raw: str) -> frozenset[str]:
    return frozenset(
        name.strip() for name in raw.split(",") if name.strip().isidentifier()
    )


def lua_declared(masked_text: str) -> frozenset[str]:
    groups = (
        *(m.group("names").split("=")[0] for m in LUA_LOCAL.finditer(masked_text)),
        *(m.group("params") for m in LUA_FUNCTION_PARAMS.finditer(masked_text)),
        *(m.group("names") for m in LUA_FOR_VARS.finditer(masked_text)),
    )
    return frozenset(name for raw in groups for name in _split_names(raw))


def _lua_global_name(line: str) -> str:
    for pattern in (LUA_GLOBAL_FUNCTION, LUA_ASSIGNMENT):
        match = pattern.match(line)
        if match and match.group("name") not in LUA_KEYWORDS:
            return match.group("name")
    return ""


def find_lua(edit: Edit) -> tuple[Finding, ...]:
    if not edit.full_file:
        return ()
    masked = mask_source(edit.text, CommentStyle.LUA)
    declared = lua_declared("\n".join(masked))
    hits = (
        Finding(
            line=index + 1,
            message=f"`{name}` is an implicit global; declare it `local`, or `local {name} <const>` in Lua 5.4",
            blocking=False,
        )
        for index, line in enumerate(masked)
        for name in [_lua_global_name(line)]
        if name and name not in declared
    )
    return suppressed_filter(edit.text, list(hits))

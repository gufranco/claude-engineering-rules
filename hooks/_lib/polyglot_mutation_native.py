from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence

from .guard_runner import Edit, Finding
from .polyglot_mutation_common import (
    CommentStyle,
    LineRule,
    NamedRule,
    mask_source,
    scan_named,
    scan_rules,
    suppressed_filter,
)

Finder = Callable[[Edit], tuple[Finding, ...]]

GO_IMPORT_SINGLE = re.compile(
    r'^\s*import\s+(?:(?P<alias>[\w.]+)\s+)?"(?P<path>[^"]+)"'
)
GO_IMPORT_IN_BLOCK = re.compile(r'^\s*(?:(?P<alias>[\w.]+)\s+)?"(?P<path>[^"]+)"\s*$')
GO_VERSION_SEGMENT = re.compile(r"^v\d+$")
GO_PACKAGE_WRITE = re.compile(
    r"^\s*(?P<pkg>[a-z]\w*)\.(?P<var>[A-Z]\w*)\s*(?:[-+*/|&^]|<<|>>)?=(?!=)"
)
GO_TOP_VAR = re.compile(
    r"^var\s+(?P<name>[a-z_]\w*)\s*(?:=\s*(?:map\[|make\(|\[\])|(?:map\[|\[\]))"
)
GO_BLOCK_VAR = re.compile(
    r"^\s+(?P<name>[a-z_]\w*)\s*(?:=\s*(?:map\[|make\(|\[\])|(?:map\[|\[\]))"
)
GO_APPEND_ASSIGN = re.compile(r"^\s*(?P<target>\w+)\s*=\s*append\(\s*(?P<source>\w+)\b")

RUST_RULES = (
    LineRule(
        pattern=re.compile(r"\bstatic\s+mut\b"),
        message="`static mut` is shared mutable state; use an atomic, `Mutex`, `OnceLock` or `LazyLock`",
    ),
    LineRule(
        pattern=re.compile(r"\b(?:RefCell|Cell|UnsafeCell)\s*<"),
        message="interior mutability; prefer an owned value or `&mut`, and state why shared mutation is needed",
        blocking=False,
    ),
)

C_EXEMPT = re.compile(
    r"\b(?:const|constexpr|constinit|volatile|extern)\b|\bREG_|\(vu\d+\s*\*\)"
)
C_TABLE_RULES = (
    NamedRule(
        pattern=re.compile(
            r"^(?:static\s+)?(?:(?:unsigned|signed|struct|enum)\s+)?[A-Za-z_][\w:]*"
            r"(?:\s*\*+\s*|\s+)(?P<name>[A-Za-z_]\w*)\s*(?:\[[^\]]*\])+\s*=\s*\{(?!\s*0?\s*\}\s*;)"
        ),
        template="file-scope table `{name}` is mutable; declare it `static const` or `constexpr` so it lives in read-only memory",
        unless=C_EXEMPT,
    ),
    NamedRule(
        pattern=re.compile(
            r"^(?:static\s+)?(?:std::)?(?:vector|array|map|unordered_map|set|unordered_set|list|deque)"
            r"\s*<[^;=]*>\s+(?P<name>\w+)\s*=?\s*\{"
        ),
        template="file-scope table `{name}` is mutable; declare it `static const` or `constexpr`",
        unless=C_EXEMPT,
    ),
)

SWIFT_RULES = (
    LineRule(
        pattern=re.compile(
            r"^\s*(?:(?:public|internal|private|fileprivate|open)\s+)?static\s+var\b"
        ),
        message="`static var` is shared mutable state across every caller; prefer `static let`",
        blocking=False,
    ),
    LineRule(
        pattern=re.compile(r"^var\s"),
        message="top-level `var` is global mutable state; prefer `let`",
        blocking=False,
    ),
)


def _go_package_name(alias: str | None, path: str) -> str:
    if alias and alias not in {"_", "."}:
        return alias
    segments = [s for s in path.split("/") if s]
    if len(segments) > 1 and GO_VERSION_SEGMENT.match(segments[-1]):
        return segments[-2]
    return segments[-1] if segments else ""


def _go_import_match(line: str, in_block: bool) -> re.Match[str] | None:
    return (GO_IMPORT_IN_BLOCK if in_block else GO_IMPORT_SINGLE).match(line)


def go_imports(raw_lines: Sequence[str]) -> frozenset[str]:
    names: set[str] = set()
    in_block = False
    for line in raw_lines:
        stripped = line.strip()
        if stripped.startswith("import ("):
            in_block = True
            continue
        if in_block and stripped == ")":
            in_block = False
        match = _go_import_match(line, in_block)
        if match:
            names = names | {
                _go_package_name(match.group("alias"), match.group("path"))
            }
    return frozenset(names)


def _var_block_lines(masked: Sequence[str]) -> frozenset[int]:
    inside: set[int] = set()
    open_block = False
    for index, line in enumerate(masked):
        if line.startswith("var ("):
            open_block = True
        elif open_block and line.startswith(")"):
            open_block = False
        elif open_block:
            inside = inside | {index}
    return frozenset(inside)


def go_shared_names(masked: Sequence[str]) -> frozenset[str]:
    block = _var_block_lines(masked)
    tops = (GO_TOP_VAR.match(line) for line in masked)
    blocked = (GO_BLOCK_VAR.match(masked[index]) for index in sorted(block))
    return frozenset(m.group("name") for m in (*tops, *blocked) if m is not None)


def _go_shared_write(line: str, name: str) -> bool:
    escaped = re.escape(name)
    return bool(
        re.search(rf"\b{escaped}\s*\[[^\]]*\]\s*(?:[-+*/|&^]|<<|>>)?=(?!=)", line)
        or re.search(rf"\b{escaped}\s*=\s*append\(\s*{escaped}\b", line)
        or re.search(rf"\b(?:delete|clear)\(\s*{escaped}\b", line)
    )


def _go_shared_hits(masked: Sequence[str]) -> Iterator[Finding]:
    shared = go_shared_names(masked)
    block = _var_block_lines(masked)
    for index, line in enumerate(masked):
        if index in block or not line[:1].isspace():
            continue
        for name in sorted(shared):
            if _go_shared_write(line, name):
                yield Finding(
                    line=index + 1,
                    message=f"package-level `{name}` is mutated inside a function; pass state in and return the new value",
                )


def _go_package_hits(
    masked: Sequence[str], imports: frozenset[str]
) -> Iterator[Finding]:
    for index, line in enumerate(masked):
        match = GO_PACKAGE_WRITE.match(line)
        if match and match.group("pkg") in imports:
            yield Finding(
                line=index + 1,
                message=f"reassigns `{match.group('pkg')}.{match.group('var')}`, another package's variable",
            )


def _go_append_hits(masked: Sequence[str], shared: frozenset[str]) -> Iterator[Finding]:
    for index, line in enumerate(masked):
        match = GO_APPEND_ASSIGN.match(line)
        if (
            match
            and match.group("target") != match.group("source")
            and match.group("target") not in shared
        ):
            yield Finding(
                line=index + 1,
                message=f"`{match.group('target')} = append({match.group('source')}, ...)` can share the backing array of `{match.group('source')}`; use `slices.Clone` first",
                blocking=False,
            )


def find_go(edit: Edit) -> tuple[Finding, ...]:
    masked = mask_source(edit.text, CommentStyle.C)
    imports = go_imports(edit.text.splitlines())
    shared = go_shared_names(masked)
    hits = [
        *_go_package_hits(masked, imports),
        *_go_shared_hits(masked),
        *_go_append_hits(masked, shared),
    ]
    return suppressed_filter(edit.text, sorted(hits, key=lambda hit: hit.line))


def find_rust(edit: Edit) -> tuple[Finding, ...]:
    return scan_rules(edit.text, CommentStyle.C, RUST_RULES)


def find_c(edit: Edit) -> tuple[Finding, ...]:
    return scan_named(edit.text, CommentStyle.C, C_TABLE_RULES)


def find_swift(edit: Edit) -> tuple[Finding, ...]:
    return scan_rules(edit.text, CommentStyle.C, SWIFT_RULES)


NATIVE_FINDERS: dict[str, Finder] = {
    ".go": find_go,
    ".rs": find_rust,
    ".c": find_c,
    ".h": find_c,
    ".cc": find_c,
    ".cpp": find_c,
    ".cxx": find_c,
    ".hh": find_c,
    ".hpp": find_c,
    ".swift": find_swift,
}

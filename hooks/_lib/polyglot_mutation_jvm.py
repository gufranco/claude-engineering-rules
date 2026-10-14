from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence

from .guard_runner import Edit, Finding
from .polyglot_mutation_common import (
    CommentStyle,
    NamedRule,
    body_line_ranges,
    mask_source,
    scan_named,
    suppressed_filter,
)

Finder = Callable[[Edit], tuple[Finding, ...]]

MUTABLE_JAVA_COLLECTIONS = (
    "ArrayList|LinkedList|HashMap|LinkedHashMap|TreeMap|HashSet|LinkedHashSet|TreeSet|"
    "ArrayDeque|ConcurrentHashMap|CopyOnWriteArrayList|EnumMap"
)
JAVA_RULES = (
    NamedRule(
        pattern=re.compile(
            r"^\s*(?:(?:public|protected)\s+)?static\s+(?!final\b|class\b|interface\b|enum\b|record\b|void\b)"
            r"(?:(?:volatile|transient)\s+)*[\w<>,.?\[\] ]+?\s+(?P<name>\w+)\s*(?:=(?!=)|;)"
        ),
        template="non-final static field `{name}` is shared mutable state; make it `static final` with an immutable value",
        unless=re.compile(r"\bprivate\b"),
    ),
    NamedRule(
        pattern=re.compile(
            rf"\bstatic\s+final\s+[\w<>,.?\[\] ]+?\s+(?P<name>\w+)\s*=\s*new\s+(?:{MUTABLE_JAVA_COLLECTIONS})\b"
        ),
        template="`{name}` is a mutable collection behind a final reference; use `List.of`, `Map.of` or `List.copyOf`",
    ),
    NamedRule(
        pattern=re.compile(
            r"\bCollections\.unmodifiable(?P<kind>List|Set|Map|Collection)\s*\("
        ),
        template="`Collections.unmodifiable{kind}` is a live view; the caller can still change it underneath. Use `{kind}.copyOf`",
        blocking=False,
    ),
)

KOTLIN_MUTABLE_TYPES = re.compile(
    r":\s*(?P<kind>MutableList|MutableMap|MutableSet|MutableCollection|ArrayList|HashMap|HashSet|LinkedHashMap)\s*<"
)
KOTLIN_DECLARATION = re.compile(
    r"^(?P<indent>\s{0,4})(?:(?:public|open|override|abstract|suspend|inline|operator)\s+)*(?:fun|val|var)\b"
)
KOTLIN_HIDDEN = re.compile(r"\b(?:private|internal|protected)\b")
KOTLIN_DATA_CLASS = re.compile(r"\bdata\s+class\s+(?P<name>\w+)[^(]*\(")

CSHARP_RULES = (
    NamedRule(
        pattern=re.compile(r"\b(?P<kind>record)\s+struct\b"),
        template="`record struct` members are writable; declare it `readonly record struct`",
        unless=re.compile(r"\breadonly\s+record\b"),
    ),
    NamedRule(
        pattern=re.compile(
            r"^\s*(?:public|protected|internal)\s+static\s+(?!readonly\b|class\b|void\b|async\b|extern\b|event\b|partial\b)"
            r"(?:volatile\s+)?[\w<>,.?\[\] ]+?\s+(?P<name>\w+)\s*(?:=(?![=>])|;)"
        ),
        template="non-readonly static field `{name}` is shared mutable state; make it `static readonly` or `const`",
    ),
    NamedRule(
        pattern=re.compile(
            r"\bpublic\s+(?:List|IList|ICollection|Dictionary|IDictionary|HashSet|ISet)\s*<.*>\s+(?P<name>\w+)\s*\{\s*get;\s*set;"
        ),
        template="collection property `{name}` has a public setter; expose `IReadOnlyList` with `init`",
        blocking=False,
    ),
)
CSHARP_RECORD = re.compile(r"\brecord\s+(?!struct\b)(?:class\s+)?(?P<name>\w+)")
CSHARP_SETTER = re.compile(r"\bset\s*;")

DART_IMMUTABLE_CLASS = re.compile(
    r"\bclass\s+(?P<name>\w+)[^{]*\bextends\s+(?:StatelessWidget|StatefulWidget)\b"
)
DART_ANNOTATED_CLASS = re.compile(r"\bclass\s+(?P<name>\w+)")
DART_FIELD = re.compile(
    r"^\s*(?!final\b|const\b|static\b|late\s+final\b|factory\b|return\b|external\b)"
    r"(?:late\s+)?(?:[A-Za-z_][\w<>,? ]*?\??\s+|var\s+)(?P<field>[a-z_]\w*)\s*(?:=(?![=>])|;)"
)
DART_RULES = (
    NamedRule(
        pattern=re.compile(r"@(?P<kind>unfreezed)\b"),
        template="`@unfreezed` generates a mutable class; use `@freezed`",
    ),
    NamedRule(
        pattern=re.compile(r"\b(?P<kind>makeCollectionsUnmodifiable)\s*:\s*false\b"),
        template="`makeCollectionsUnmodifiable: false` exposes mutable collections from a freezed class",
    ),
)


def find_java(edit: Edit) -> tuple[Finding, ...]:
    return scan_named(edit.text, CommentStyle.C, JAVA_RULES)


def _matching_paren(text: str, start: int) -> int:
    depth = 0
    for index in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[index], 0)
        if depth == 0:
            return index
    return len(text)


def _kotlin_data_class_hits(masked_text: str) -> Iterator[Finding]:
    for match in KOTLIN_DATA_CLASS.finditer(masked_text):
        params = masked_text[
            match.end() - 1 : _matching_paren(masked_text, match.end() - 1)
        ]
        if re.search(r"\bvar\b", params):
            yield Finding(
                line=masked_text.count("\n", 0, match.start()) + 1,
                message=f"data class `{match.group('name')}` has a `var` property; use `val` and `copy()`",
            )


def _kotlin_signature_hits(masked: Sequence[str]) -> Iterator[Finding]:
    for index, line in enumerate(masked):
        kind = KOTLIN_MUTABLE_TYPES.search(line)
        if kind and KOTLIN_DECLARATION.match(line) and not KOTLIN_HIDDEN.search(line):
            yield Finding(
                line=index + 1,
                message=f"public API exposes `{kind.group('kind')}`; expose a read-only `List`, `Map` or `Set`",
            )


def find_kotlin(edit: Edit) -> tuple[Finding, ...]:
    masked = mask_source(edit.text, CommentStyle.C)
    hits = [
        *_kotlin_data_class_hits("\n".join(masked)),
        *_kotlin_signature_hits(masked),
    ]
    return suppressed_filter(edit.text, sorted(hits, key=lambda hit: hit.line))


def _record_setter_hits(masked: Sequence[str]) -> Iterator[Finding]:
    for start, end in body_line_ranges(masked, CSHARP_RECORD):
        name = CSHARP_RECORD.search(masked[start])
        for index in range(start, end + 1):
            if name and CSHARP_SETTER.search(masked[index]):
                yield Finding(
                    line=index + 1,
                    message=f"record `{name.group('name')}` declares a `set` accessor; use `init`",
                )


def find_csharp(edit: Edit) -> tuple[Finding, ...]:
    masked = mask_source(edit.text, CommentStyle.C)
    hits = [
        *scan_named(edit.text, CommentStyle.C, CSHARP_RULES),
        *_record_setter_hits(masked),
    ]
    return suppressed_filter(edit.text, sorted(hits, key=lambda hit: hit.line))


def _dart_class_name(masked: Sequence[str], index: int) -> str:
    widget = DART_IMMUTABLE_CLASS.search(masked[index])
    if widget:
        return widget.group("name")
    previous = [line.strip() for line in masked[:index] if line.strip()]
    annotated = DART_ANNOTATED_CLASS.search(masked[index])
    if annotated and previous and previous[-1] == "@immutable":
        return annotated.group("name")
    return ""


def _depth_one_lines(masked: Sequence[str], start: int, end: int) -> Iterator[int]:
    depth = 0
    for index in range(start, end + 1):
        if depth == 1 and index > start:
            yield index
        depth += masked[index].count("{") - masked[index].count("}")


def _dart_field_hits(masked: Sequence[str]) -> Iterator[Finding]:
    for start, end in body_line_ranges(masked, DART_ANNOTATED_CLASS):
        name = _dart_class_name(masked, start)
        fields = (
            (index, DART_FIELD.match(masked[index]))
            for index in (_depth_one_lines(masked, start, end) if name else ())
        )
        for index, field in fields:
            if field:
                yield Finding(
                    line=index + 1,
                    message=f"field `{field.group('field')}` in immutable class `{name}` is not `final`",
                )


def find_dart(edit: Edit) -> tuple[Finding, ...]:
    masked = mask_source(edit.text, CommentStyle.C)
    hits = [
        *scan_named(edit.text, CommentStyle.C, DART_RULES),
        *_dart_field_hits(masked),
    ]
    return suppressed_filter(edit.text, sorted(hits, key=lambda hit: hit.line))


JVM_FINDERS: dict[str, Finder] = {
    ".java": find_java,
    ".kt": find_kotlin,
    ".kts": find_kotlin,
    ".cs": find_csharp,
    ".dart": find_dart,
}

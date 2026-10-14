from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from .guard_runner import Finding
from .polyglot_mutation_common import CommentStyle, mask_source, suppressed_filter

DEDUP_NAME = re.compile(
    r"(?:processed|seen|handled|dedup|deduped|duplicate|dupe|idempoten|delivered|"
    r"consumed|acked|acknowledged|alreadyseen|alreadyprocessed|emitted|notified|sent)",
    re.IGNORECASE,
)
SINGLE_FLIGHT_NAME = re.compile(
    r"(?:inflight|in_flight|pending|ongoing|running)", re.IGNORECASE
)

SKIP_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    ".d.ts",
    "_test.py",
    ".test.py",
    "_test.go",
    "test.java",
    "test.kt",
    "tests.cs",
    "test.cs",
    "_spec.rb",
    "_test.rb",
    "_test.dart",
    "_test.exs",
    "_test.clj",
)
SKIP_SEGMENTS = (
    "/__tests__/",
    "/__test__/",
    "/test/",
    "/tests/",
    "/spec/",
    "/migrations/",
    "/migration/",
    "/seeds/",
    "/seed/",
    "/fixtures/",
    "/node_modules/",
    "/vendor/",
    "/.claude/hooks/",
)


@dataclass(frozen=True, slots=True)
class Declaration:
    style: CommentStyle | None
    pattern: re.Pattern[str]


JS_DECLARATION = Declaration(
    CommentStyle.C,
    re.compile(
        r"^(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)(?:\s*:\s*[^=]+)?\s*=\s*"
        r"(?:new\s+(?:Set|Map|WeakSet|WeakMap)\b|\[\s*\])"
    ),
)
DECLARATIONS: dict[str, Declaration] = {
    **dict.fromkeys((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"), JS_DECLARATION),
    ".py": Declaration(
        CommentStyle.HASH,
        re.compile(
            r"^(?P<name>[A-Za-z_]\w*)\s*(?::\s*[^=]+)?=\s*"
            r"(?:set\s*\(|dict\s*\(|\{\s*\}|\[\s*\]|defaultdict\s*\(|deque\s*\(|OrderedDict\s*\()"
        ),
    ),
    ".go": Declaration(
        CommentStyle.C,
        re.compile(
            r"^var\s+(?P<name>\w+)\s*(?:=\s*(?:map\[|make\(\s*map\[|\[\])|map\[|sync\.Map\b|\[\])"
        ),
    ),
    ".java": Declaration(
        CommentStyle.C,
        re.compile(
            r"\b(?:private|protected|public|static)\b[^=;(]*\b(?:Set|Map|List|Collection|Queue|HashSet|"
            r"HashMap|ConcurrentHashMap|ConcurrentMap)\s*<[^=;]*>\s+(?P<name>\w+)\s*="
        ),
    ),
    ".kt": Declaration(
        CommentStyle.C,
        re.compile(
            r"^\s{0,4}(?:(?:private|protected|internal|public)\s+)?(?:val|var)\s+(?P<name>\w+)\s*(?::[^=]+)?=\s*"
            r"(?:mutableSetOf|mutableMapOf|mutableListOf|hashSetOf|hashMapOf|HashSet|HashMap|"
            r"ConcurrentHashMap|LinkedHashSet)\b"
        ),
    ),
    ".cs": Declaration(
        CommentStyle.C,
        re.compile(
            r"\b(?:private|protected|public|internal|static)\b[^=;(]*\b(?:HashSet|Dictionary|"
            r"ConcurrentDictionary|List|ISet|IDictionary|ConcurrentBag)\s*<[^=;]*>\s+(?P<name>\w+)\s*="
        ),
    ),
    ".rb": Declaration(
        CommentStyle.HASH,
        re.compile(
            r"^\s*(?P<name>[A-Z][A-Z0-9_]*|@@\w+)\s*=\s*"
            r"(?:Set\.new|\{\s*\}|\[\s*\]|Hash\.new|Concurrent::(?:Set|Map|Hash)\.new)"
        ),
    ),
    ".dart": Declaration(
        CommentStyle.C,
        re.compile(
            r"^\s{0,2}(?:static\s+)?(?:final\s+|var\s+|late\s+)?(?:(?:Set|Map|List|HashSet|HashMap)\s*<[^>]*>\s+)?"
            r"(?P<name>[a-z_]\w*)\s*=\s*(?:<[^>]*>\s*)?"
            r"(?:\{\s*\}|\[\s*\]|(?:Set|Map|HashSet|HashMap|LinkedHashSet)\s*(?:<[^>]*>)?\s*[.(])"
        ),
    ),
    ".rs": Declaration(
        CommentStyle.C,
        re.compile(
            r"\bstatic\s+(?P<name>[A-Z_]\w*)\s*:[^=]*\b(?:HashSet|HashMap|BTreeSet|DashSet|DashMap)\b"
        ),
    ),
    ".ex": Declaration(CommentStyle.HASH, re.compile(r":ets\.new\(\s*:(?P<name>\w+)")),
    ".exs": Declaration(CommentStyle.HASH, re.compile(r":ets\.new\(\s*:(?P<name>\w+)")),
    ".clj": Declaration(
        None,
        re.compile(
            r"\(def\s+(?P<name>[\w\-?!*]+)\s+\(atom\s+(?:#\{|\{\}|\[\]|\(hash-set\))"
        ),
    ),
}

MESSAGES = {
    ".ex": "ETS table `{name}` dies with its owner process",
    ".exs": "ETS table `{name}` dies with its owner process",
}
DEFAULT_MESSAGE = "in-memory deduplication store `{name}`"


def is_dedup_source(path: str) -> bool:
    lowered = path.lower()
    if PurePosixPath(lowered).suffix not in DECLARATIONS or lowered.endswith(
        SKIP_SUFFIXES
    ):
        return False
    return not any(segment in lowered for segment in SKIP_SEGMENTS)


def _usage_pattern(name: str) -> re.Pattern[str]:
    n = re.escape(name)
    return re.compile(
        rf"(?<![\w\-$]){n}(?![\w\-$])\s*(?:\.\s*\w|\[|<<)|\bin\s+{n}\b|@{n}(?![\w\-])|"
        rf"insert_new\(\s*:{n}\b|swap!\s+{n}(?![\w\-])"
    )


def _is_dedup_name(name: str) -> bool:
    return bool(DEDUP_NAME.search(name)) and not SINGLE_FLIGHT_NAME.search(name)


def _used_elsewhere(lines: Sequence[str], declared_at: int, name: str) -> bool:
    usage = _usage_pattern(name)
    return any(
        usage.search(line) for index, line in enumerate(lines) if index != declared_at
    )


def _declarations(
    lines: Sequence[str], pattern: re.Pattern[str]
) -> Iterator[tuple[int, str]]:
    for index, line in enumerate(lines):
        match = pattern.search(line)
        if match and _is_dedup_name(match.group("name")):
            yield index, match.group("name")


def find(path: str, text: str) -> tuple[Finding, ...]:
    suffix = PurePosixPath(path.lower()).suffix
    declaration = DECLARATIONS[suffix]
    lines = (
        text.splitlines()
        if declaration.style is None
        else mask_source(text, declaration.style)
    )
    template = MESSAGES.get(suffix, DEFAULT_MESSAGE)
    hits = [
        Finding(line=index + 1, message=template.format(name=name))
        for index, name in _declarations(lines, declaration.pattern)
        if _used_elsewhere(lines, index, name)
    ]
    return suppressed_filter(text, hits)

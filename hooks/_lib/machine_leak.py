from __future__ import annotations

import difflib
import re
from collections.abc import Iterable
from dataclasses import dataclass

from _lib.machine_identity import Identifier, Kind

PUBLIC_KINDS = frozenset({Kind.USERNAME, Kind.REAL_NAME, Kind.EMAIL})
FORGE_KINDS = frozenset({Kind.USERNAME, Kind.ACCOUNT})
MANIFEST_FILE = re.compile(
    r"^(?:package\.json|pyproject\.toml|Cargo\.toml|setup\.cfg|composer\.json|"
    r"library\.properties|marketplace\.json|plugin\.json|.+\.gemspec)$"
)
IDENTITY_FILE = re.compile(
    r"^(?:LICEN[CS]E|COPYING|AUTHORS|CONTRIBUTORS|NOTICE|CODEOWNERS|FUNDING|"
    r"CODE_OF_CONDUCT|SECURITY|CITATION)(?:[._-].*)?$",
    re.IGNORECASE,
)
AUTHORSHIP_LINE = re.compile(
    r"copyright|SPDX-|\N{COPYRIGHT SIGN}|\(c\)|\bauthors?\b|\bmaintainers?\b|"
    r"given-names|family-names|\balias:|\bowner\b|\bpublisher\b|approved_by|^From: ",
    re.IGNORECASE,
)
FORGE_BEFORE = re.compile(
    r"(?:(?:github|gitlab|codeberg|bitbucket)\.(?:com|org)[/:]|@|\brepos/)$",
    re.IGNORECASE,
)
URL_BEFORE = re.compile(r"https?://\S*$")
COMPOUND_AFTER = re.compile(r"^-[A-Za-z]")
FORGE_AFTER = re.compile(r"^/\S")
SKIPPED_SEGMENTS = ("vendor/", "node_modules/", "third_party/", ".git/")
EDGE = "A-Za-z0-9"
ADDING_OPCODES = frozenset({"insert", "replace"})

Line = tuple[str, int, str]


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    line: int
    kind: Kind
    token: str


def _pattern(identifiers: list[Identifier]) -> re.Pattern[str]:
    tokens = sorted({i.token for i in identifiers}, key=len, reverse=True)
    alternation = "|".join(re.escape(token) for token in tokens)
    return re.compile(rf"(?<![{EDGE}])(?:{alternation})(?![{EDGE}])", re.IGNORECASE)


def _skipped(path: str) -> bool:
    return any(path.startswith(s) or f"/{s}" in path for s in SKIPPED_SEGMENTS)


def _forge_handle(text: str, match: re.Match[str]) -> bool:
    before, after = text[: match.start()], text[match.end() :]
    if FORGE_BEFORE.search(before) or URL_BEFORE.search(before):
        return True
    if after.startswith("@users.noreply.") or COMPOUND_AFTER.match(after):
        return True
    return bool(FORGE_AFTER.match(after)) and not before.endswith("/")


def _authorship(path: str, text: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if IDENTITY_FILE.match(name) or MANIFEST_FILE.match(name):
        return True
    return AUTHORSHIP_LINE.search(text) is not None


def _allowed(kind: Kind, path: str, text: str, match: re.Match[str]) -> bool:
    if kind in PUBLIC_KINDS and _authorship(path, text):
        return True
    return kind in FORGE_KINDS and _forge_handle(text, match)


def scan_lines(lines: Iterable[Line], identifiers: list[Identifier]) -> list[Finding]:
    if not identifiers:
        return []
    kinds = {i.token.lower(): i.kind for i in identifiers}
    pattern = _pattern(identifiers)
    found: list[Finding] = []
    for path, number, text in lines:
        if _skipped(path):
            continue
        for match in pattern.finditer(text):
            kind = kinds[match.group(0).lower()]
            if not _allowed(kind, path, text, match):
                found = [*found, Finding(path, number, kind, match.group(0))]
    return found


def added_lines(path: str, before: str, after: str) -> list[Line]:
    old, new = before.splitlines(), after.splitlines()
    opcodes = difflib.SequenceMatcher(a=old, b=new).get_opcodes()
    spans = [(j1, j2) for tag, _i1, _i2, j1, j2 in opcodes if tag in ADDING_OPCODES]
    return [(path, j + 1, new[j]) for j1, j2 in spans for j in range(j1, j2)]

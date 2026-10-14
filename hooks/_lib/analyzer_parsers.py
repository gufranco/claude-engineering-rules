from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawFinding:
    path: str
    line: int
    rule: str
    message: str


Parsed = tuple[RawFinding, ...] | None

CLANG_TIDY_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):\d+: (?:warning|error): (?P<message>.+?) \[(?P<rule>[\w.\-]+)(?:,[^\]]*)?\]$",
    re.MULTILINE,
)
LUACHECK_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):\d+: \((?P<rule>[EW]\d+)\) (?P<message>.+)$",
    re.MULTILINE,
)
DART_FIELDS = 8


def _json(output: str) -> object | None:
    try:
        parsed: object = json.loads(output)
    except ValueError:
        return None
    return parsed


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _sequence(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _from_json(
    output: str, extract: Callable[[object], Iterable[RawFinding]]
) -> Parsed:
    data = _json(output)
    if data is None:
        return None
    return tuple(extract(data))


def parse_clang_tidy(output: str) -> Parsed:
    return tuple(
        RawFinding(
            m.group("path"), int(m.group("line")), m.group("rule"), m.group("message")
        )
        for m in CLANG_TIDY_LINE.finditer(output)
    )


def parse_luacheck(output: str) -> Parsed:
    return tuple(
        RawFinding(
            m.group("path"), int(m.group("line")), m.group("rule"), m.group("message")
        )
        for m in LUACHECK_LINE.finditer(output)
    )


def parse_dart(output: str) -> Parsed:
    rows = (line.split("|", DART_FIELDS - 1) for line in output.splitlines())
    return tuple(
        RawFinding(row[3], int(row[4]), row[2], row[7])
        for row in rows
        if len(row) == DART_FIELDS and row[4].isdigit()
    )


def _golangci_issues(data: object) -> Iterable[RawFinding]:
    for issue in _sequence(_mapping(data).get("Issues")):
        item = _mapping(issue)
        position = _mapping(item.get("Pos"))
        yield RawFinding(
            str(position.get("Filename")),
            int(str(position.get("Line"))),
            str(item.get("FromLinter")),
            str(item.get("Text")),
        )


def parse_golangci(output: str) -> Parsed:
    first = output.strip().splitlines()[0] if output.strip() else ""
    return _from_json(first, _golangci_issues)


def _ruff_items(data: object) -> Iterable[RawFinding]:
    for entry in _sequence(data):
        item = _mapping(entry)
        location = _mapping(item.get("location"))
        yield RawFinding(
            str(item.get("filename")),
            int(str(location.get("row"))),
            str(item.get("code")),
            str(item.get("message")),
        )


def parse_ruff(output: str) -> Parsed:
    return _from_json(output, _ruff_items)


def _pyright_items(data: object) -> Iterable[RawFinding]:
    for entry in _sequence(_mapping(data).get("generalDiagnostics")):
        item = _mapping(entry)
        start = _mapping(_mapping(item.get("range")).get("start"))
        rule = str(item.get("rule") or "pyright")
        yield RawFinding(
            str(item.get("file")),
            int(str(start.get("line"))) + 1,
            rule,
            str(item.get("message")),
        )


def parse_pyright(output: str) -> Parsed:
    return _from_json(output, _pyright_items)


def _rubocop_items(data: object) -> Iterable[RawFinding]:
    for entry in _sequence(_mapping(data).get("files")):
        item = _mapping(entry)
        for offense in _sequence(item.get("offenses")):
            found = _mapping(offense)
            location = _mapping(found.get("location"))
            yield RawFinding(
                str(item.get("path")),
                int(str(location.get("line"))),
                str(found.get("cop_name")),
                str(found.get("message")),
            )


def parse_rubocop(output: str) -> Parsed:
    return _from_json(output, _rubocop_items)


def _pmd_items(data: object) -> Iterable[RawFinding]:
    for entry in _sequence(_mapping(data).get("files")):
        item = _mapping(entry)
        for violation in _sequence(item.get("violations")):
            found = _mapping(violation)
            yield RawFinding(
                str(item.get("filename")),
                int(str(found.get("beginline"))),
                str(found.get("rule")),
                str(found.get("description")),
            )


def parse_pmd(output: str) -> Parsed:
    return _from_json(output, _pmd_items)


def _swiftlint_items(data: object) -> Iterable[RawFinding]:
    for entry in _sequence(data):
        item = _mapping(entry)
        yield RawFinding(
            str(item.get("file")),
            int(str(item.get("line"))),
            str(item.get("rule_id")),
            str(item.get("reason")),
        )


def parse_swiftlint(output: str) -> Parsed:
    return _from_json(output, _swiftlint_items)


def parse_checkstyle(output: str) -> Parsed:
    try:
        root = ElementTree.fromstring(output)
    except ElementTree.ParseError:
        return None
    return tuple(
        RawFinding(
            file.get("name", ""),
            int(error.get("line", "0")),
            error.get("source", "").removeprefix("detekt."),
            error.get("message", ""),
        )
        for file in root.iter("file")
        for error in file.iter("error")
    )

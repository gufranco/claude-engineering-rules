from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from enum import Enum

FULL_COVERAGE = 100.0
CONTEXT_LINES = 15

_PRAGMA = "pragma"
_IGNORE = "ignore"
INLINE_EXCLUSION = re.compile(
    rf"{_PRAGMA}:\s*no\s*(?:cover|branch)\b"
    rf"|\b(?:istanbul|c8|v8)\s+{_IGNORE}\b"
    rf"|\bnode:coverage\s+(?:disable|{_IGNORE})\b"
    r"|\bcoverage:\s*ignore(?:-(?:line|start|end|file))?\b"
    r"|#\[\s*coverage\s*\(\s*off\s*\)\s*\]"
    r"|\[\s*(?:assembly:\s*)?ExcludeFromCodeCoverage\b"
    r"|@codeCoverageIgnore\b"
    r"|\bLCOV_EXCL_(?:LINE|START|STOP|BR_LINE|BR_START|BR_STOP)\b"
    r"|:nocov:",
    re.IGNORECASE,
)

PROSE_SUFFIXES = (".md", ".mdx", ".markdown", ".rst", ".txt", ".adoc")

CONFIG_NAMES = frozenset(
    {
        ".coveragerc",
        "setup.cfg",
        "tox.ini",
        "pytest.ini",
        "pyproject.toml",
        "package.json",
        ".nycrc",
        ".nycrc.json",
        ".nycrc.yml",
        ".nycrc.yaml",
        ".c8rc",
        ".c8rc.json",
        "codecov.yml",
        ".codecov.yml",
        "Makefile",
        "justfile",
        ".simplecov",
    }
)
CONFIG_PREFIXES = (
    "jest.config.",
    "vitest.config.",
    "vite.config.",
    "vitest.workspace.",
)
WORKFLOW_DIR = re.compile(
    r"(^|/)\.github/workflows/[^/]+\.ya?ml$|(^|/)\.gitlab-ci\.ya?ml$"
)

THRESHOLD = re.compile(
    r"\bfail_under\s*=\s*(\d+(?:\.\d+)?)"
    r"|--(?:cov-)?fail-under[=\s]+(\d+(?:\.\d+)?)"
    r"|--test-coverage-(?:lines|branches|functions)=(\d+(?:\.\d+)?)"
    r"|--(?:lines|branches|functions|statements)[=\s]+(\d+(?:\.\d+)?)"
    r"|[\"']?\b(?:lines|branches|functions|statements)[\"']?\s*:\s*(\d+(?:\.\d+)?)"
    r"|\bminimum_coverage\s+(\d+(?:\.\d+)?)"
    r"|\btarget:\s*(\d+(?:\.\d+)?)%",
)
EXCLUSION_KEY = re.compile(
    r"\b(?:omit|exclude|exclude_lines|exclude_also|coveragePathIgnorePatterns"
    r"|test-coverage-exclude|add_filter|ignore)\b",
    re.IGNORECASE,
)
PATH_LIKE = re.compile(r"[*/][\w.*/-]*|\.\w{1,5}\b")


class Action(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class Verdict:
    action: Action
    problems: tuple[str, ...]


ALLOWED = Verdict(Action.ALLOW, ())


def is_prose(path: str) -> bool:
    return path.lower().endswith(PROSE_SUFFIXES)


def is_coverage_config(path: str) -> bool:
    name = os.path.basename(path)
    return (
        name in CONFIG_NAMES
        or name.startswith(CONFIG_PREFIXES)
        or bool(WORKFLOW_DIR.search(path))
    )


def inline_exclusions(text: str) -> int:
    return len(INLINE_EXCLUSION.findall(text))


def thresholds(text: str) -> list[float]:
    return [
        float(next(group for group in match.groups() if group is not None))
        for match in THRESHOLD.finditer(text)
    ]


def added_lines(before: str, after: str) -> list[tuple[int, str]]:
    old = before.splitlines()
    new = after.splitlines()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    return [
        (index, new[index])
        for tag, _, _, start, end in matcher.get_opcodes()
        if tag in ("replace", "insert")
        for index in range(start, end)
    ]


def _in_exclusion_context(lines: list[str], index: int) -> bool:
    window = lines[max(0, index - CONTEXT_LINES) : index + 1]
    return any(EXCLUSION_KEY.search(line) for line in window)


def _threshold_problems(added: list[tuple[int, str]]) -> list[str]:
    return [
        f"line {index + 1} sets a coverage threshold of {value:g}, below 100"
        for index, line in added
        for value in thresholds(line)
        if value < FULL_COVERAGE
    ]


def _exclusion_entries(after: str, added: list[tuple[int, str]]) -> list[str]:
    lines = after.splitlines()
    return [
        f"line {index + 1}: {line.strip()}"
        for index, line in added
        if PATH_LIKE.search(line) and _in_exclusion_context(lines, index)
    ]


def config_verdict(before: str, after: str) -> Verdict:
    added = added_lines(before, after)
    problems = _threshold_problems(added)
    if problems:
        return Verdict(Action.BLOCK, tuple(problems))
    entries = _exclusion_entries(after, added)
    return Verdict(Action.ASK, tuple(entries)) if entries else ALLOWED


def source_verdict(before: str, after: str) -> Verdict:
    added = inline_exclusions(after) - inline_exclusions(before)
    if added <= 0:
        return ALLOWED
    return Verdict(
        Action.BLOCK,
        (f"adds {added} coverage exclusion directive{'s' if added > 1 else ''}",),
    )


def verdict_for(path: str, before: str, after: str) -> Verdict:
    if is_prose(path):
        return ALLOWED
    source = source_verdict(before, after)
    if source.action is Action.BLOCK or not is_coverage_config(path):
        return source
    return config_verdict(before, after)

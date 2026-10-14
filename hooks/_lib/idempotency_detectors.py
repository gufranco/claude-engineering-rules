from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from .guard_runner import Edit, Finding
from .polyglot_mutation_common import CommentStyle, mask_source, suppressed_filter

SHELL_SUFFIXES = frozenset({".sh", ".bash", ".zsh"})
SHELL_BASENAMES = frozenset(
    {
        ".zshrc",
        ".bashrc",
        ".bash_profile",
        ".zprofile",
        ".zshenv",
        ".profile",
        ".zlogin",
    }
)
TERRAFORM_SUFFIXES = frozenset({".tf", ".hcl"})
CODE_STYLES = {
    **dict.fromkeys(
        (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".java", ".kt", ".cs"),
        CommentStyle.C,
    ),
    ".py": CommentStyle.HASH,
    ".rb": CommentStyle.HASH,
}
SKIP_SEGMENTS = (
    "/test/",
    "/tests/",
    "/__tests__/",
    "/spec/",
    "/fixtures/",
    "/node_modules/",
    "/vendor/",
    "/.claude/hooks/",
)
SKIP_MARKERS = re.compile(r"(?:\.test\.|\.spec\.|_test\.|_spec\.|\.bats$)")

COMMAND_START = r"(?:^|[;&|]\s*|\b(?:then|do|else)\s+)(?:sudo\s+)?"
SHELL_GUARDED = re.compile(r"\b(?:if|until|while)\b|\|\|")
MKDIR = re.compile(COMMAND_START + r"mkdir\s+(?!(?:[^;&|]*\s)?(?:-\w*p\b|--parents))")
LINK = re.compile(
    COMMAND_START + r"ln\s+(?=(?:[^;&|]*\s)?-\w*s)(?!(?:[^;&|]*\s)?(?:-\w*f|--force))"
)
RC_APPEND = re.compile(
    r">>\s*[\"']?(?:(?:~|\$HOME|\$\{HOME\})/\.(?:zshrc|bashrc|bash_profile|profile|zprofile|zshenv)\b|/etc/)"
)
GREP_GUARD = re.compile(r"\bgrep\s+-\w*q")
PATH_PREPEND = re.compile(r"\bPATH=[^;]*\$\{?PATH\b")
PATH_DEDUPED = re.compile(r"\btypeset\s+-\w*U\w*\s+(?:path|PATH)\b|\":\$PATH:\"")

TIMESTAMP = re.compile(r"\btimestamp\(\s*\)")
UUID = re.compile(r"\buuid\(\s*\)")
PROVISIONER = re.compile(r"\bprovisioner\s+\"(?:local|remote)-exec\"")
IGNORE_ALL = re.compile(r"\bignore_changes\s*=\s*all\b")

KAFKA_IDEMPOTENCE_OFF = re.compile(
    r"\bidempotent\s*:\s*false\b|[\"']?enable\.idempotence[\"']?\s*[:=,]\s*[\"']?(?:false|False)\b|"
    r"ENABLE_IDEMPOTENCE_CONFIG\s*,\s*\"?false\b"
)
BULLMQ_JOB_ID = re.compile(r"\bjobId\b")
BULLMQ_REMOVE = re.compile(r"\bremoveOnComplete\s*:\s*true\b")


@dataclass(frozen=True, slots=True)
class Lines:
    raw: Sequence[str]
    masked: Sequence[str]


def _kind(path: str) -> str:
    pure = PurePosixPath(path.lower())
    if pure.suffix in SHELL_SUFFIXES or pure.name in SHELL_BASENAMES:
        return "shell"
    if pure.suffix in TERRAFORM_SUFFIXES:
        return "terraform"
    return "code" if pure.suffix in CODE_STYLES else ""


def applies_to(path: str) -> bool:
    lowered = path.lower()
    if not _kind(lowered) or SKIP_MARKERS.search(lowered):
        return False
    return not any(segment in lowered for segment in SKIP_SEGMENTS)


def _lines(text: str, style: CommentStyle) -> Lines:
    raw = text.splitlines()
    masked = mask_source(text, style)
    return Lines(raw=raw, masked=masked + [""] * (len(raw) - len(masked)))


def _shell_command_hits(lines: Lines) -> Iterator[Finding]:
    for index, line in enumerate(lines.masked):
        if SHELL_GUARDED.search(line):
            continue
        if MKDIR.search(line):
            yield Finding(
                line=index + 1,
                message="`mkdir` fails when the directory exists; use `mkdir -p`",
            )
        if LINK.search(line):
            yield Finding(
                line=index + 1,
                message="`ln -s` fails when the link exists; use `ln -sfn`",
            )


def _guarded_nearby(raw: Sequence[str], index: int, guard: re.Pattern[str]) -> bool:
    return any(guard.search(line) for line in raw[max(0, index - 3) : index + 1])


def _shell_append_hits(lines: Lines) -> Iterator[Finding]:
    for index, raw in enumerate(lines.raw):
        if (
            ">>" in lines.masked[index]
            and RC_APPEND.search(raw)
            and not _guarded_nearby(lines.raw, index, GREP_GUARD)
        ):
            yield Finding(
                line=index + 1,
                message="re-running appends the line again; guard it with `grep -qxF '<line>' <file> ||`",
            )


def _shell_path_hits(lines: Lines, text: str) -> Iterator[Finding]:
    if PATH_DEDUPED.search(text):
        return
    for index, raw in enumerate(lines.raw):
        if "PATH=" in lines.masked[index] and PATH_PREPEND.search(raw):
            yield Finding(
                line=index + 1,
                message='extending PATH on every source duplicates entries; add `typeset -U path` in zsh or a `case ":$PATH:"` guard',
                blocking=False,
            )


def find_shell(edit: Edit) -> list[Finding]:
    lines = _lines(edit.text, CommentStyle.HASH)
    return [
        *_shell_command_hits(lines),
        *_shell_append_hits(lines),
        *_shell_path_hits(lines, edit.text),
    ]


TERRAFORM_RULES: tuple[tuple[re.Pattern[str], str, bool], ...] = (
    (
        TIMESTAMP,
        "`timestamp()` changes on every run, so the plan never converges; use `plantimestamp()` or a `time_static` resource",
        True,
    ),
    (
        UUID,
        "`uuid()` changes on every run, so the plan never converges; use a `random_uuid` resource",
        True,
    ),
    (
        PROVISIONER,
        "provisioner runs only at create time and Terraform cannot model its effect; prefer a provider resource",
        False,
    ),
    (
        IGNORE_ALL,
        "`ignore_changes = all` hides every drift from the plan; list the attributes instead",
        False,
    ),
)


TERRAFORM_COMMENT = re.compile(r"^\s*(?:#|//)")


def find_terraform(edit: Edit) -> list[Finding]:
    return [
        Finding(line=index + 1, message=message, blocking=blocking)
        for index, line in enumerate(edit.text.splitlines())
        if not TERRAFORM_COMMENT.match(line)
        for pattern, message, blocking in TERRAFORM_RULES
        if pattern.search(line)
    ]


def _code_line_hits(raw: str, masked: str) -> Iterator[tuple[str, bool]]:
    if not masked.strip():
        return
    if KAFKA_IDEMPOTENCE_OFF.search(raw):
        yield (
            "disables the Kafka idempotent producer; a retried send can write a duplicate",
            True,
        )
    if BULLMQ_JOB_ID.search(raw) and BULLMQ_REMOVE.search(raw):
        yield (
            "`removeOnComplete: true` deletes the job and reopens its `jobId` dedup window; keep it with `removeOnComplete: { age: <seconds> }`",
            False,
        )


def find_code(edit: Edit) -> list[Finding]:
    style = CODE_STYLES[PurePosixPath(edit.path.lower()).suffix]
    lines = _lines(edit.text, style)
    return [
        Finding(line=index + 1, message=message, blocking=blocking)
        for index, (raw, masked) in enumerate(zip(lines.raw, lines.masked))
        for message, blocking in _code_line_hits(raw, masked)
    ]


FINDERS = {"shell": find_shell, "terraform": find_terraform, "code": find_code}


def find(edit: Edit) -> tuple[Finding, ...]:
    hits = FINDERS[_kind(edit.path)](edit)
    return suppressed_filter(edit.text, sorted(hits, key=lambda hit: hit.line))

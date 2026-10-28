#!/usr/bin/env python3
import os
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.hook_warning import emit_warning  # noqa: E402

from _lib.audit_log import record as _audit  # noqa: E402


sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.hook_profile import should_run  # noqa: E402


BYPASS_ENV = "DOCKERFILE_QUALITY_DISABLE"

DOCKERFILE_BASENAMES = {"dockerfile"}
DOCKERFILE_SUFFIXES = {".dockerfile"}
COMPOSE_PATTERN = re.compile(
    r"^(?:docker-compose|compose)(?:\.[\w.-]+)?\.ya?ml$", re.IGNORECASE
)


COPY_OR_ADD = re.compile(r"^\s*(?:COPY|ADD)\s+(?P<rest>.+)$", re.IGNORECASE)
SENSITIVE_SOURCE = re.compile(
    r"(?:^|/)(?:\.env(?:\.[^/\s]+)?|[^/\s]*\.(?:pem|key|crt|p12|pfx)"
    r"|id_rsa(?:\.[^/\s]+)?|id_ed25519(?:\.[^/\s]+)?)$",
    re.IGNORECASE,
)
DOCUMENTATION_SUFFIXES = (".example", ".sample", ".template")


def _copy_sources(line: str) -> list[str]:
    match = COPY_OR_ADD.match(line)
    if not match:
        return []
    rest = match.group("rest").strip()
    if rest.startswith("["):
        try:
            operands = [str(item) for item in json.loads(rest)]
        except ValueError:
            return rest.split()
    else:
        operands = [token for token in rest.split() if not token.startswith("--")]
    return operands[:-1]


def sensitive_sources(line: str) -> list[str]:
    return [
        source
        for source in _copy_sources(line)
        if SENSITIVE_SOURCE.search(source)
        and not source.lower().endswith(DOCUMENTATION_SUFFIXES)
    ]


SECRET_ENV_ARG = re.compile(
    r"""
    ^\s*(?P<kw>ENV|ARG)\s+
    (?P<name>
        (?:[A-Z][A-Z0-9_]*_)?           # optional prefix
        (?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|PRIVATE_KEY|ACCESS_KEY|AUTH_KEY)
        (?:_[A-Z0-9_]+)?                # optional suffix
    )
    \s*=\s*
    (?P<value>[^\s$].*?)                # value that does NOT start with $ (env interp)
    \s*$
    """,
    re.VERBOSE,
)

COMPOSE_PRIVILEGED = re.compile(r"^\s*privileged:\s*true\b", re.IGNORECASE)
COMPOSE_HOST_NS = re.compile(
    r"^\s*(pid|ipc|network_mode|userns_mode):\s*['\"]?host\b", re.IGNORECASE
)

FROM_BAD_TAG = re.compile(
    r"^\s*FROM\s+(?:--platform=\S+\s+)?(?P<image>\S+?)(?::(?P<tag>latest|lts))?(?:\s+AS\s+\S+)?\s*$",
    re.IGNORECASE,
)

ROOT_USERS = frozenset({"root", "0", "root:root", "0:0"})

COMPOSE_VERSION = re.compile(r"^version:\s*['\"]?[\d.]+['\"]?\s*$")

COMPOSE_ENV_LITERAL_SECRET = re.compile(
    r"""
    ^\s*
    (?:-\s*)?                                 # list-form prefix
    (?P<name>
        (?:[A-Z][A-Z0-9_]*_)?
        (?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|PRIVATE_KEY|ACCESS_KEY|AUTH_KEY)
        (?:_[A-Z0-9_]+)?
    )
    \s*[:=]\s*
    (?P<value>[^\s$\"'{].+?)                   # literal value, not $VAR or ${VAR}
    \s*$
    """,
    re.VERBOSE,
)


def detect_kind(path: str) -> str:
    if not path:
        return "other"
    name = Path(path).name
    lower = name.lower()
    if lower in DOCKERFILE_BASENAMES:
        return "dockerfile"
    for suffix in DOCKERFILE_SUFFIXES:
        if lower.endswith(suffix):
            return "dockerfile"
    if lower.startswith("dockerfile."):
        return "dockerfile"
    if COMPOSE_PATTERN.match(name):
        return "compose"
    return "other"


def extract_new_content(tool_name: str, tool_input: dict) -> tuple[str, bool]:
    if tool_name == "Write":
        return tool_input.get("content", "") or "", True
    if tool_name == "Edit":
        return tool_input.get("new_string", "") or "", False
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        parts = []
        for edit in edits:
            new = edit.get("new_string", "") or ""
            if new:
                parts.append(new)
        return "\n".join(parts), False
    return "", False


USER_DIRECTIVE = re.compile(r"^\s*USER\s+(\S+)", re.IGNORECASE)
COMPOSE_COMMENT = re.compile(r"#.*$")
COMPOSE_ENVIRONMENT = re.compile(r"^(\s*)environment:\s*$")
FLOATING_TAGS = frozenset({"latest", "lts"})
PIN_ADVICE = "Pin by digest (FROM image:tag@sha256:...). "

CodeLine = tuple[int, str, str]


def _dockerfile_code_lines(text: str) -> list[CodeLine]:
    stripped = [
        (i, raw, raw.split("#", 1)[0].rstrip())
        for i, raw in enumerate(text.splitlines(), 1)
    ]
    return [entry for entry in stripped if entry[2]]


def _dockerfile_block(entry: CodeLine) -> str | None:
    i, raw, line = entry
    if sensitive_sources(line):
        instruction = line.split(maxsplit=1)[0].upper()
        return (
            f"line {i}: {instruction} of sensitive file. "
            "Move it to .dockerignore and inject at runtime, or use "
            "RUN --mount=type=secret for build-time access. "
            f"Source: {raw.strip()}"
        )
    m = SECRET_ENV_ARG.match(line)
    if not m:
        return None
    return (
        f"line {i}: {m.group('kw')} {m.group('name')} has a literal "
        "value and persists in image history. Use "
        "RUN --mount=type=secret,id=<name> for build-time secrets. "
        f"Source: {raw.strip()}"
    )


def _from_warning(i: int, raw: str, from_match: re.Match[str]) -> str | None:
    image = from_match.group("image")
    tag = from_match.group("tag")
    if tag and tag.lower() in FLOATING_TAGS:
        return (
            f"line {i}: FROM uses floating tag '{tag}'. "
            f"{PIN_ADVICE}Source: {raw.strip()}"
        )
    if ":" not in image and "@" not in image:
        return f"line {i}: FROM has no tag or digest. {PIN_ADVICE}Source: {raw.strip()}"
    return None


def _final_stage_warnings(
    user_directives: list[tuple[int, str]], last_from_line: int
) -> list[str]:
    final_users = [value for num, value in user_directives if num > last_from_line]
    if not final_users:
        return [
            "no USER directive in the final stage. "
            "Add a non-root USER (numeric UID preferred)."
        ]
    if final_users[-1].lower() in ROOT_USERS:
        return [
            "the final stage runs as root. "
            "Set a non-root USER (numeric UID preferred) after the last FROM."
        ]
    return []


def _user_warnings(
    user_directives: list[tuple[int, str]], from_lines: list[int], full_file: bool
) -> list[str]:
    if full_file:
        if not from_lines:
            return []
        return _final_stage_warnings(user_directives, from_lines[-1])
    return [
        f"line {line_num}: USER {value} switches to root; "
        "the final stage must run as a non-root user."
        for line_num, value in user_directives
        if value.lower() in ROOT_USERS
    ]


def scan_dockerfile(text: str, full_file: bool) -> tuple[list[str], list[str]]:
    classified = [
        (entry, _dockerfile_block(entry)) for entry in _dockerfile_code_lines(text)
    ]
    blocks = [block for _, block in classified if block]
    rest = [entry for entry, block in classified if block is None]
    froms = [(i, raw, m) for i, raw, line in rest if (m := FROM_BAD_TAG.match(line))]
    users = [
        (i, m.group(1)) for i, _, line in rest if (m := USER_DIRECTIVE.match(line))
    ]
    from_warns = [w for i, raw, m in froms if (w := _from_warning(i, raw, m))]
    from_lines = [i for i, _, _ in froms]
    return blocks, from_warns + _user_warnings(users, from_lines, full_file)


def _compose_block(i: int, raw: str, no_comment: str) -> str | None:
    if COMPOSE_PRIVILEGED.match(no_comment):
        return (
            f"line {i}: privileged: true. CIS Docker 5.4. "
            "Use cap_add for the specific capability instead. "
            f"Source: {raw.strip()}"
        )
    if COMPOSE_HOST_NS.match(no_comment):
        return (
            f"line {i}: host namespace toggle. "
            "Defeats container isolation. "
            f"Source: {raw.strip()}"
        )
    return None


def _environment_warning(i: int, raw: str, no_comment: str) -> str | None:
    m = COMPOSE_ENV_LITERAL_SECRET.match(no_comment)
    if not m:
        return None
    return (
        f"line {i}: environment block contains a literal "
        f"value for {m.group('name')}. "
        "Use top-level secrets: with file or environment "
        "source and consume via *_FILE convention. "
        f"Source: {raw.strip()}"
    )


def _version_warning(i: int) -> str:
    return (
        f"line {i}: top-level 'version:' key is deprecated under Compose v2. Remove it."
    )


def scan_compose(text: str, full_file: bool) -> tuple[list[str], list[str]]:
    blocks: list[str] = []
    warns: list[str] = []
    environment_indent = -1
    for i, raw in enumerate(text.splitlines(), 1):
        no_comment = COMPOSE_COMMENT.sub("", raw)
        block = _compose_block(i, raw, no_comment) if no_comment.strip() else None
        if not no_comment.strip() or block:
            blocks = [*blocks, block] if block else blocks
            continue
        if COMPOSE_VERSION.match(no_comment):
            warns = [*warns, _version_warning(i)]
            continue
        opened = COMPOSE_ENVIRONMENT.match(no_comment)
        if opened or environment_indent < 0:
            environment_indent = len(opened.group(1)) if opened else environment_indent
            continue
        if len(no_comment) - len(no_comment.lstrip()) <= environment_indent:
            environment_indent = -1
            continue
        warning = _environment_warning(i, raw, no_comment)
        warns = [*warns, warning] if warning else warns
    _ = full_file
    return blocks, warns


def _disabled() -> bool:
    return (
        os.environ.get(BYPASS_ENV) == "1"
        or is_bypassed("dockerfile-compose-quality")
        or not should_run("dockerfile-compose-quality")
    )


def _block(file_path: str, tool_name: str, blocks: list[str]) -> None:
    print(
        "BLOCKED: dockerfile-compose-quality on {0}:".format(file_path),
        file=sys.stderr,
    )
    for b in blocks:
        print(f"  {b}", file=sys.stderr)
    print(
        f"Bypass for emergencies: export {BYPASS_ENV}=1 in the parent shell.",
        file=sys.stderr,
    )
    print("Reference: standards/container-security.md", file=sys.stderr)
    _audit(
        hook="dockerfile-compose-quality",
        decision="block",
        tool=tool_name,
        reason="; ".join(b.split(":", 1)[0] for b in blocks),
        command_excerpt=file_path[:240],
    )
    sys.exit(2)


def main() -> None:
    if _disabled():
        sys.exit(0)
    data = read_hook_payload("dockerfile-compose-quality")
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", data.get("input", {})) or {}
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        sys.exit(0)
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    kind = detect_kind(file_path)
    if kind == "other":
        sys.exit(0)
    text, full_file = extract_new_content(tool_name, tool_input)
    if not text:
        sys.exit(0)
    scanner = scan_dockerfile if kind == "dockerfile" else scan_compose
    blocks, warns = scanner(text, full_file)
    if blocks:
        _block(file_path, tool_name, blocks)
    if warns:
        emit_warning(
            f"WARN dockerfile-compose-quality on {file_path}:\n"
            + "\n".join(f"  {w}" for w in warns)
        )
    sys.exit(0)


if __name__ == "__main__":
    main()

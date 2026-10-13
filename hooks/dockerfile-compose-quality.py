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

try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # type: ignore  # noqa: E402
except ImportError:  # pragma: no cover

    def should_run(_id: str) -> bool:  # type: ignore
        return True


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


def scan_dockerfile(text: str, full_file: bool) -> tuple[list[str], list[str]]:
    blocks: list[str] = []
    warns: list[str] = []
    lines = text.splitlines()

    user_directives: list[tuple[int, str]] = []
    from_directives: list[int] = []

    for i, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0].rstrip()
        if not line:
            continue

        if sensitive_sources(line):
            instruction = line.split(maxsplit=1)[0].upper()
            blocks.append(
                f"line {i}: {instruction} of sensitive file. "
                "Move it to .dockerignore and inject at runtime, or use "
                "RUN --mount=type=secret for build-time access. "
                f"Source: {raw.strip()}"
            )
            continue

        m = SECRET_ENV_ARG.match(line)
        if m:
            blocks.append(
                f"line {i}: {m.group('kw')} {m.group('name')} has a literal "
                "value and persists in image history. Use "
                "RUN --mount=type=secret,id=<name> for build-time secrets. "
                f"Source: {raw.strip()}"
            )
            continue

        from_match = FROM_BAD_TAG.match(line)
        if from_match:
            from_directives.append(i)
            image = from_match.group("image")
            tag = from_match.group("tag")
            if tag and tag.lower() in {"latest", "lts"}:
                warns.append(
                    f"line {i}: FROM uses floating tag '{tag}'. "
                    "Pin by digest (FROM image:tag@sha256:...). "
                    f"Source: {raw.strip()}"
                )
            elif ":" not in image and "@" not in image:
                warns.append(
                    f"line {i}: FROM has no tag or digest. "
                    "Pin by digest (FROM image:tag@sha256:...). "
                    f"Source: {raw.strip()}"
                )

        user_match = re.match(r"^\s*USER\s+(\S+)", line, re.IGNORECASE)
        if user_match:
            user_directives.append((i, user_match.group(1)))

    if full_file and from_directives:
        last_from_line = from_directives[-1]
        final_user = None
        for line_num, user_value in user_directives:
            if line_num > last_from_line:
                final_user = user_value
        if final_user is None:
            warns.append(
                "no USER directive in the final stage. "
                "Add a non-root USER (numeric UID preferred)."
            )
        elif final_user.lower() in ROOT_USERS:
            warns.append(
                "the final stage runs as root. "
                "Set a non-root USER (numeric UID preferred) after the last FROM."
            )
    if not full_file:
        warns.extend(
            f"line {line_num}: USER {value} switches to root; "
            "the final stage must run as a non-root user."
            for line_num, value in user_directives
            if value.lower() in ROOT_USERS
        )

    return blocks, warns


def scan_compose(text: str, full_file: bool) -> tuple[list[str], list[str]]:
    blocks: list[str] = []
    warns: list[str] = []
    lines = text.splitlines()
    in_environment = False
    environment_indent = -1

    for i, raw in enumerate(lines, 1):
        no_comment = re.sub(r"#.*$", "", raw)
        stripped = no_comment.strip()
        if not stripped:
            continue

        if COMPOSE_PRIVILEGED.match(no_comment):
            blocks.append(
                f"line {i}: privileged: true. CIS Docker 5.4. "
                "Use cap_add for the specific capability instead. "
                f"Source: {raw.strip()}"
            )
            continue

        if COMPOSE_HOST_NS.match(no_comment):
            blocks.append(
                f"line {i}: host namespace toggle. "
                "Defeats container isolation. "
                f"Source: {raw.strip()}"
            )
            continue

        if COMPOSE_VERSION.match(no_comment):
            warns.append(
                f"line {i}: top-level 'version:' key is deprecated under Compose v2. "
                "Remove it."
            )
            continue

        env_block_match = re.match(r"^(\s*)environment:\s*$", no_comment)
        if env_block_match:
            in_environment = True
            environment_indent = len(env_block_match.group(1))
            continue
        if in_environment:
            current_indent = len(no_comment) - len(no_comment.lstrip())
            if no_comment.strip() and current_indent <= environment_indent:
                in_environment = False
                environment_indent = -1
            else:
                m = COMPOSE_ENV_LITERAL_SECRET.match(no_comment)
                if m:
                    warns.append(
                        f"line {i}: environment block contains a literal "
                        f"value for {m.group('name')}. "
                        "Use top-level secrets: with file or environment "
                        "source and consume via *_FILE convention. "
                        f"Source: {raw.strip()}"
                    )

    _ = full_file
    return blocks, warns


def main() -> None:
    if os.environ.get(BYPASS_ENV) == "1":
        sys.exit(0)
    if is_bypassed("dockerfile-compose-quality"):
        sys.exit(0)
    if not should_run("dockerfile-compose-quality"):
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

    if kind == "dockerfile":
        blocks, warns = scan_dockerfile(text, full_file)
    else:
        blocks, warns = scan_compose(text, full_file)

    if blocks:
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
        print(
            "Reference: standards/container-security.md",
            file=sys.stderr,
        )
        _audit(
            hook="dockerfile-compose-quality",
            decision="block",
            tool=tool_name,
            reason="; ".join(b.split(":", 1)[0] for b in blocks),
            command_excerpt=file_path[:240],
        )
        sys.exit(2)

    if warns:
        emit_warning(
            f"WARN dockerfile-compose-quality on {file_path}:\n"
            + "\n".join(f"  {w}" for w in warns)
        )
    sys.exit(0)


if __name__ == "__main__":
    main()

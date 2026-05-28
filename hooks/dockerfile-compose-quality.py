#!/usr/bin/env python3
"""Pre-write quality and security hook for Dockerfile and Compose files.

Fires on PreToolUse for Write, Edit, and MultiEdit. Activates only when the
target file path matches a Dockerfile or Compose pattern.

BLOCKs four high-confidence dangerous patterns:
    1. COPY of `.env*`, key, cert, or SSH-key files
    2. ENV/ARG that names a secret and has a literal value
    3. Compose `privileged: true`
    4. Compose `pid: host`, `ipc: host`, `network_mode: host`, `userns_mode: host`

WARNs on four lower-confidence smells:
    1. `FROM image:latest`, `FROM image:lts`, or `FROM image` with no tag
    2. `USER root` in the final stage, or missing non-root `USER` on Write
    3. Compose top-level `version:` (deprecated under Compose v2)
    4. Compose `environment:` block with a literal secret-named value

Bypass for the whole hook: set `DOCKERFILE_QUALITY_DISABLE=1` in the parent
shell.

Receives the tool input as JSON on stdin.
Exit 0 = allow (may print warnings to stderr).
Exit 2 = block.

Conforms to the hook conventions used by `docker-context-guard.py` and
`secret-scanner.py`. Pure stdlib, no YAML parser dependency.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
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

# File kind detection.
DOCKERFILE_BASENAMES = {"dockerfile"}
DOCKERFILE_SUFFIXES = {".dockerfile"}
COMPOSE_PATTERN = re.compile(
    r"^(?:docker-compose|compose)(?:\.[\w.-]+)?\.ya?ml$", re.IGNORECASE
)

# BLOCK patterns shared between Dockerfile and Compose are evaluated by kind.

# BLOCK 1: COPY of sensitive files. Captures the offending path.
SENSITIVE_COPY = re.compile(
    r"""
    ^\s*COPY\s+                       # COPY keyword
    (?:--[\w-]+(?:=[^\s]+)?\s+)*      # optional flags like --chown, --from, --link
    (
        \.env(?:\.[^\s]+)?            # .env or .env.<anything>
        | \S*\.(?:pem|key|crt|p12|pfx) # cert/key extensions anywhere in the name
        | id_rsa(?:\.[^\s]+)?         # SSH keys
        | id_ed25519(?:\.[^\s]+)?
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# BLOCK 2: ENV or ARG that names a secret AND has a literal value.
# Allow `$VAR` references (`ENV TOKEN=$BUILD_TOKEN`) and empty defaults.
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

# BLOCK 3-4: Compose dangerous toggles.
COMPOSE_PRIVILEGED = re.compile(r"^\s*privileged:\s*true\b", re.IGNORECASE)
COMPOSE_HOST_NS = re.compile(
    r"^\s*(pid|ipc|network_mode|userns_mode):\s*['\"]?host\b", re.IGNORECASE
)

# WARN 1: FROM image:latest/lts or no tag.
FROM_BAD_TAG = re.compile(
    r"^\s*FROM\s+(?:--platform=\S+\s+)?(?P<image>\S+?)(?::(?P<tag>latest|lts))?(?:\s+AS\s+\S+)?\s*$",
    re.IGNORECASE,
)

# WARN 2: USER root in final stage.
USER_ROOT = re.compile(r"^\s*USER\s+(?:root|0)\s*$", re.IGNORECASE)

# WARN 3: Compose top-level `version:` key.
COMPOSE_VERSION = re.compile(r"^version:\s*['\"]?[\d.]+['\"]?\s*$")

# WARN 4: Compose `environment:` literal secret. Best-effort detection.
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
    """Return 'dockerfile', 'compose', or 'other' based on the file path."""
    if not path:
        return "other"
    name = Path(path).name
    lower = name.lower()
    if lower in DOCKERFILE_BASENAMES:
        return "dockerfile"
    for suffix in DOCKERFILE_SUFFIXES:
        if lower.endswith(suffix):
            return "dockerfile"
    # Heuristic: anything starting with "Dockerfile" is a Dockerfile fragment.
    if lower.startswith("dockerfile."):
        return "dockerfile"
    if COMPOSE_PATTERN.match(name):
        return "compose"
    return "other"


def extract_new_content(tool_name: str, tool_input: dict) -> tuple[str, bool]:
    """Return the text the tool would persist or add.

    Second element is True when the text represents the FULL post-change file
    (Write), False when it is an additive fragment (Edit / MultiEdit).
    """
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
    """Return (blocks, warns) for a Dockerfile fragment or full file."""
    blocks: list[str] = []
    warns: list[str] = []
    lines = text.splitlines()

    user_directives: list[tuple[int, str]] = []
    from_directives: list[int] = []

    for i, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0].rstrip()  # drop inline comments
        if not line:
            continue

        if SENSITIVE_COPY.match(line):
            blocks.append(
                f"line {i}: COPY of sensitive file. "
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

        if USER_ROOT.match(line):
            warns.append(
                f"line {i}: USER root in the final stage. "
                "Set a non-root UID (numeric preferred). "
                f"Source: {raw.strip()}"
            )

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

    # Full-file final-stage USER check on Write only. Edit fragments cannot
    # determine final-stage ownership without parsing the whole file.
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
        elif final_user in {"root", "0"}:
            # already reported per-line, no duplicate
            pass

    return blocks, warns


def scan_compose(text: str, full_file: bool) -> tuple[list[str], list[str]]:
    """Return (blocks, warns) for a Compose YAML fragment or full file."""
    blocks: list[str] = []
    warns: list[str] = []
    lines = text.splitlines()
    in_environment = False
    environment_indent = -1

    for i, raw in enumerate(lines, 1):
        # Drop YAML comments
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

        # Track entry/exit of an environment: block by indentation.
        # Only line-level heuristic; full YAML parsing is out of scope here.
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

    # Discard 'full_file' here; the warnings above do not need full-file context.
    _ = full_file
    return blocks, warns


def main() -> None:
    if os.environ.get(BYPASS_ENV) == "1":
        sys.exit(0)
    if not should_run("dockerfile-compose-quality"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

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

    if warns:
        print(
            "WARN dockerfile-compose-quality on {0}:".format(file_path),
            file=sys.stderr,
        )
        for w in warns:
            print(f"  {w}", file=sys.stderr)

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

    sys.exit(0)


if __name__ == "__main__":
    main()

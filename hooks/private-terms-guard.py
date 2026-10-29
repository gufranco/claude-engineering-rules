#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.audit_log import record as _audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402
from _lib.staged_blobs import (  # noqa: E402
    StagedScanError,
    commit_request,
    staged_documents,
)

HOOK = "private-terms-guard"
BYPASS_ENV = "PRIVATE_TERMS_GUARD_DISABLE"
TERMS_ENV = "PRIVATE_TERMS_FILE"
REPO_ENV = "PRIVATE_TERMS_REPO"
VAULT_ENV = "SECOND_BRAIN_VAULT"
VAULT_TERMS = ".private-terms.txt"
GIT_TIMEOUT_SECONDS = 20
GUIDANCE = (
    "\n\nThis repository is public. Rewrite the text so it names no employer, "
    "colleague, client, private project, or personal detail: describe the "
    "mechanism generically. The history behind a rule belongs in the vault, per "
    "~/.claude/standards/rule-provenance.md. The denylist lives in the vault at "
    f"{VAULT_TERMS}. Bypass once with {BYPASS_ENV}=1 in the parent shell."
)


def terms_file() -> Path | None:
    explicit = os.environ.get(TERMS_ENV, "").strip()
    if explicit:
        return Path(explicit).expanduser()
    vault = os.environ.get(VAULT_ENV, "").strip()
    return Path(vault).expanduser() / VAULT_TERMS if vault else None


def load_terms() -> tuple[str, ...]:
    source = terms_file()
    if source is None:
        return ()
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()
    stripped = (line.strip() for line in lines)
    return tuple(line for line in stripped if line and not line.startswith("#"))


def term_pattern(terms: tuple[str, ...]) -> re.Pattern[str]:
    ordered = sorted(terms, key=len, reverse=True)
    alternatives = "|".join(re.escape(term) for term in ordered)
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.I)


def repo_root() -> Path:
    configured = os.environ.get(REPO_ENV, "").strip()
    base = Path(configured) if configured else Path(__file__).resolve().parents[1]
    return base.resolve()


def _git(directory: Path | str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )


def published_path(root: Path, file_path: str) -> str | None:
    if not file_path:
        return None
    path = Path(file_path).expanduser().resolve()
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    ignored = _git(root, "check-ignore", "-q", str(path)).returncode == 0
    return None if ignored else relative.as_posix()


def hits(pattern: re.Pattern[str], label: str, text: str) -> list[str]:
    found = sorted({match.group(0).lower() for match in pattern.finditer(text)})
    return [f"  - {label}: {term}" for term in found]


def edit_findings(
    pattern: re.Pattern[str], root: Path, tool: str, tool_input: Mapping[str, object]
) -> list[str]:
    label = published_path(root, str(tool_input.get("file_path") or ""))
    if label is None:
        return []
    return [
        hit
        for _field, text in payload_fragments(tool, tool_input)
        for hit in hits(pattern, label, text)
    ]


def toplevel(directory: str) -> Path | None:
    result = _git(directory, "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else None


def commit_findings(
    pattern: re.Pattern[str], root: Path, tool_input: Mapping[str, object], cwd: str
) -> list[str]:
    command = tool_input.get("command")
    request = commit_request(command, cwd) if isinstance(command, str) else None
    if request is None or toplevel(request.directory) != root:
        return []
    return [
        hit
        for document in staged_documents(request)
        for hit in hits(pattern, document.path, document.after)
    ]


def findings_for(
    payload: Mapping[str, object], pattern: re.Pattern[str], root: Path
) -> list[str]:
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        return []
    if tool == "Bash":
        cwd = str(payload.get("cwd") or os.getcwd())
        return commit_findings(pattern, root, tool_input, cwd)
    return edit_findings(pattern, root, tool, tool_input)


def block(message: str, reason: str) -> int:
    print(message, file=sys.stderr)
    _audit(hook=HOOK, decision="block", reason=reason)
    return 2


def read_payload() -> dict[str, object] | None:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def main() -> int:
    if os.environ.get(BYPASS_ENV) == "1" or is_bypassed(HOOK):
        return 0
    payload = read_payload()
    if payload is None:
        return block(
            f"Blocked: {HOOK} could not read its input, so the change was not "
            f"checked for private terms. Bypass once with {BYPASS_ENV}=1.",
            "unreadable hook input",
        )
    terms = load_terms()
    if not terms:
        return 0
    try:
        found = findings_for(payload, term_pattern(terms), repo_root())
    except StagedScanError as error:
        return block(
            f"Blocked: {HOOK} could not read the staged files: {error}" + GUIDANCE,
            "staged scan failed",
        )
    if not found:
        return 0
    return block(
        "Blocked: private terms in a public repository file.\n"
        + "\n".join(found)
        + GUIDANCE,
        "private term in public file",
    )


if __name__ == "__main__":
    sys.exit(main())

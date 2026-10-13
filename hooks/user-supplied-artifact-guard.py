#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.git_invocation import strip_git_global_options  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.output import block as _block  # noqa: E402

try:
    from _lib.audit_log import record as _audit_record
except Exception:  # noqa: BLE001
    _audit_record = None  # type: ignore[assignment]

HOOK_NAME = "user-supplied-artifact-guard"
ENV_DISABLE = "USER_SUPPLIED_ARTIFACT_DISABLE"
GIT_TIMEOUT_SECONDS = 5
HASH_CHUNK_BYTES = 65536

_GIT_PREFIX = r"\bgit\s+(?:-\S+\s+(?:[^-\s]\S*\s+)?)*"
COMMIT_PATTERN = re.compile(_GIT_PREFIX + r"commit\b")
ADD_PATTERN = re.compile(_GIT_PREFIX + r"add\b(?P<args>[^&|;]*)")

MANIFEST_NAMES = (
    "artifacts.manifest.json",
    "docs/artifacts.manifest.json",
    ".github/artifacts.manifest.json",
)

ARTIFACT_EXTENSIONS = frozenset(
    {
        ".3ds",
        ".a26",
        ".a78",
        ".bios",
        ".cdi",
        ".chd",
        ".cia",
        ".cso",
        ".fds",
        ".gba",
        ".gbc",
        ".gcm",
        ".gdi",
        ".gguf",
        ".int",
        ".iso",
        ".lnx",
        ".n64",
        ".nds",
        ".nsp",
        ".pbp",
        ".pce",
        ".rom",
        ".rvz",
        ".safetensors",
        ".sfc",
        ".smc",
        ".swc",
        ".v64",
        ".wbfs",
        ".wud",
        ".wux",
        ".xci",
        ".z64",
    }
)


def _read_command() -> str:
    data = read_hook_payload("user-supplied-artifact-guard")
    tool_input = tool_input_of(data)
    cmd = tool_input.get("command", "")
    return cmd if isinstance(cmd, str) else ""


def _git(args: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def _staged_files() -> list[str]:
    return _git(["diff", "--cached", "--name-only"])


def _split_args(raw: str) -> list[str]:
    try:
        return shlex.split(raw)
    except ValueError:
        return raw.split()


def _explicit_add_paths(command: str) -> list[str]:
    paths: list[str] = []
    for match in ADD_PATTERN.finditer(strip_git_global_options(command)):
        for token in _split_args(match.group("args")):
            if not token or token.startswith("-"):
                continue
            if token in {".", "..", "*"}:
                continue
            paths.append(token)
    return paths


def _repo_root() -> Path:
    lines = _git(["rev-parse", "--show-toplevel"])
    return Path(lines[0]) if lines else Path.cwd()


def _collect_manifest_claims(node: object, digests: set[str], sizes: set[int]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "sha256" and isinstance(value, str) and len(value) == 64:
                digests.add(value.lower())
            elif key == "size" and isinstance(value, int) and value >= 0:
                sizes.add(value)
            else:
                _collect_manifest_claims(value, digests, sizes)
    elif isinstance(node, list):
        for item in node:
            _collect_manifest_claims(item, digests, sizes)


def _manifest_claims(root: Path) -> tuple[set[str], set[int]]:
    digests: set[str] = set()
    sizes: set[int] = set()
    for name in MANIFEST_NAMES:
        path = root / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        _collect_manifest_claims(data, digests, sizes)
    return digests, sizes


def _sha256(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _resolve(name: str, root: Path) -> Path | None:
    candidate = Path(name)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    for base in (root, Path.cwd()):
        resolved = base / name
        if resolved.is_file():
            return resolved
    return None


def _classify(
    name: str,
    root: Path,
    digests: set[str],
    sizes: set[int],
) -> str | None:
    path = _resolve(name, root)
    if path is None:
        return None
    if digests:
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        if size in sizes:
            actual = _sha256(path)
            if actual is not None and actual in digests:
                return f"SHA-256 {actual[:12]} is declared in the artifacts manifest"
    if path.suffix.lower() in ARTIFACT_EXTENSIONS:
        return f"{path.suffix.lower()} is a user-supplied artifact extension"
    return None


def _audit(command: str, offenders: list[tuple[str, str]]) -> None:
    if _audit_record is None:
        return
    try:
        _audit_record(
            hook=HOOK_NAME,
            decision="block",
            decision_class="block",
            reason=f"{len(offenders)} user-supplied artifact(s) about to enter git",
            tool="Bash",
            command_excerpt=command[:200],
        )
    except Exception as error:  # noqa: BLE001
        sys.stderr.write(f"{HOOK_NAME}: audit log write failed: {error}\n")


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if not should_run(HOOK_NAME):
        return 0
    if is_bypassed(HOOK_NAME):
        return 0

    command = _read_command()
    candidates: list[str] = []
    if COMMIT_PATTERN.search(strip_git_global_options(command)):
        candidates.extend(_staged_files())
    candidates.extend(_explicit_add_paths(command))
    if not candidates:
        return 0

    root = _repo_root()
    digests, sizes = _manifest_claims(root)

    offenders: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        reason = _classify(name, root, digests, sizes)
        if reason is not None:
            offenders.append((name, reason))
    if not offenders:
        return 0

    detected = "\n".join(
        [f"{len(offenders)} user-supplied artifact(s) about to enter git history:"]
        + [f"  {name}: {reason}" for name, reason in offenders]
    )
    message = _block(
        hook=HOOK_NAME,
        rule_anchor="standards/artifact-identity.md (Never Become a Distribution Channel)",
        detected=detected,
        why=(
            "The project requires this file but may not distribute it. The user "
            "supplies their own copy. Committing it republishes someone else's "
            "work, and git history keeps it forever even after a later deletion."
        ),
        fix=(
            "Unstage the file and ignore the path:\n"
            "  bad:  git add game.gba && git commit\n"
            "  good: git rm --cached game.gba && echo 'game.gba' >> .gitignore\n"
            "Publish the file's identity instead of the file: add size, CRC32, "
            "SHA-1, and SHA-256 to artifacts.manifest.json so the user can "
            "confirm their own copy is the right one."
        ),
        bypass_when=(
            "The file is genuinely redistributable: your own asset, a public-domain "
            "dump, or content you hold the rights to. Confirm the license with the "
            "user before bypassing, since this one is hard to undo."
        ),
        decision="STOP-AND-ASK",
        env_var=ENV_DISABLE,
        safety="further artifacts in the same session will not be blocked.",
    )
    sys.stderr.write(message)
    _audit(command, offenders)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

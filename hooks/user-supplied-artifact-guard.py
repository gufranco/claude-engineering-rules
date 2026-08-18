#!/usr/bin/env python3
"""PreToolUse Bash hook: keep user-supplied artifacts out of git history.

Some projects require a file the project may not distribute: a game ROM,
a console BIOS, vendor firmware, licensed model weights. The user supplies
their own copy. Committing that copy turns the repository into a
redistribution channel for someone else's work.

Two independent signals:

1. Manifest digest. When the repository ships an artifacts manifest, any
   staged file whose SHA-256 matches a declared digest is exactly the file
   the manifest says the user must supply. Zero false positives. File size
   acts as a cheap pre-filter so hashing runs only on exact-size matches.
2. Extension. A staged path carrying an unambiguous ROM, disc-image,
   firmware, or model-weight extension. Ambiguous extensions such as
   ``.bin``, ``.img``, and ``.md`` are deliberately absent; the manifest
   signal covers those.

Scope: ``git commit`` reads the staged set, which is exactly what enters
history. ``git add`` is checked only for explicit path arguments, because
bulk forms such as ``git add -A`` cannot be resolved before git runs.
Commit remains the authoritative gate.

Every manifest found is read and merged rather than stopping at the first,
so a project that splits declarations across locations stays covered.

Rule source: ``rules/artifact-identity.md``.

Bypass channels:
    1. Env var `USER_SUPPLIED_ARTIFACT_DISABLE=1` (parent shell).
    2. File registry entry for hook `user-supplied-artifact-guard`.
"""

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

from _lib.bypass import is_bypassed  # noqa: E402
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
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    tool_input = data.get("tool_input") or data.get("input") or {}
    if not isinstance(tool_input, dict):
        return ""
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
    """Split an argument string, honoring quotes when the string is balanced.

    A path containing spaces survives as one token. Unbalanced quotes fall
    back to whitespace splitting so a partial command still gets checked.
    """
    try:
        return shlex.split(raw)
    except ValueError:
        return raw.split()


def _explicit_add_paths(command: str) -> list[str]:
    """Return path-like arguments of every `git add` in `command`.

    Flags and bulk selectors are dropped: they name no single path, so the
    commit gate handles them instead.
    """
    paths: list[str] = []
    for match in ADD_PATTERN.finditer(command):
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
    """Walk a decoded manifest and gather every sha256 and size it declares.

    Shape-tolerant on purpose. A project may extend the schema, and a
    stricter reader would silently stop protecting the new entries.
    """
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
    """Return the first existing file `name` can refer to.

    Staged paths from git are repo-root-relative. Paths typed into a
    `git add` are relative to the working directory, which is not the repo
    root whenever the command runs from a subdirectory.
    """
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
    """Return a reason string when `name` is a user-supplied artifact."""
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
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if not should_run(HOOK_NAME):
        return 0
    if is_bypassed(HOOK_NAME):
        return 0

    command = _read_command()
    candidates: list[str] = []
    if COMMIT_PATTERN.search(command):
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
        rule_anchor="rules/artifact-identity.md (Never Become a Distribution Channel)",
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

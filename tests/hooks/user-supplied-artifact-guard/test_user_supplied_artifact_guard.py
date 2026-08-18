"""Tests for `hooks/user-supplied-artifact-guard.py`.

Observable behavior:
- Ignores Bash commands that are neither `git add` nor `git commit`.
- Blocks `git commit` when a staged file carries a user-supplied artifact
  extension, or when its SHA-256 matches an entry in the project manifest.
- Blocks `git add` when an explicit path argument is such an artifact.
- Leaves ordinary source and documentation files alone, `.md` included.
- Bypass via env var or file registry returns 0 immediately.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "user-supplied-artifact-guard.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402
from _lib.output import validate_block_message  # noqa: E402

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


@pytest.fixture()
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    subprocess.run(
        ["git", "init", "-q", str(tmp_path)],
        check=True,
        env={**os.environ, **GIT_ENV},
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write(repo: Path, name: str, payload: bytes) -> Path:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


def _stage(repo: Path, name: str, payload: bytes) -> Path:
    target = _write(repo, name, payload)
    subprocess.run(["git", "add", "--", name], check=True, cwd=str(repo))
    return target


def _manifest(repo: Path, payload: bytes, *, label: str = "base-rom") -> None:
    digest = hashlib.sha256(payload).hexdigest()
    body = {
        "version": 1,
        "artifacts": [
            {
                "id": label,
                "accepted": [{"size": len(payload), "sha256": digest}],
            }
        ],
    }
    (repo / "artifacts.manifest.json").write_text(json.dumps(body), encoding="utf-8")


def test_ignores_non_git_command(git_repo: Path, tool_use, assert_allows) -> None:
    _stage(git_repo, "game.gba", b"rom-bytes")

    payload = tool_use("Bash", {"command": "ls -la"})

    assert_allows(HOOK, payload)


def test_allows_ordinary_staged_files(git_repo: Path, tool_use, assert_allows) -> None:
    _stage(git_repo, "src/index.ts", b"export const x = 1;\n")

    payload = tool_use("Bash", {"command": "git commit -m 'feat: add x'"})

    assert_allows(HOOK, payload)


def test_ignores_markdown_extension(git_repo: Path, tool_use, assert_allows) -> None:
    _stage(git_repo, "docs/guide.md", b"# Guide\n")

    payload = tool_use("Bash", {"command": "git commit -m 'docs: add guide'"})

    assert_allows(HOOK, payload)


def test_blocks_commit_of_artifact_extension(
    git_repo: Path, tool_use, assert_blocks
) -> None:
    _stage(git_repo, "roms/game.gba", b"rom-bytes")

    payload = tool_use("Bash", {"command": "git commit -m 'chore: add rom'"})

    _code, stderr = assert_blocks(HOOK, payload, "roms/game.gba")
    assert "user-supplied-artifact-guard" in stderr


def test_blocks_commit_when_digest_matches_manifest(
    git_repo: Path, tool_use, assert_blocks
) -> None:
    body = b"the-exact-artifact-bytes"
    _manifest(git_repo, body)
    _stage(
        git_repo,
        "artifacts.manifest.json",
        (git_repo / "artifacts.manifest.json").read_bytes(),
    )
    _stage(git_repo, "assets/blob.dat", body)

    payload = tool_use("Bash", {"command": "git commit -m 'chore: assets'"})

    _code, stderr = assert_blocks(HOOK, payload, "assets/blob.dat")
    assert "manifest" in stderr


def test_allows_commit_when_manifest_has_no_match(
    git_repo: Path, tool_use, assert_allows
) -> None:
    _manifest(git_repo, b"the-exact-artifact-bytes")
    _stage(git_repo, "notes.txt", b"unrelated content of a different length")

    payload = tool_use("Bash", {"command": "git commit -m 'docs: notes'"})

    assert_allows(HOOK, payload)


def test_allows_same_size_but_different_content(
    git_repo: Path, tool_use, assert_allows
) -> None:
    body = b"the-exact-artifact-bytes"
    _manifest(git_repo, body)
    _stage(git_repo, "notes.txt", b"x" * len(body))

    payload = tool_use("Bash", {"command": "git commit -m 'docs: notes'"})

    assert_allows(HOOK, payload)


def test_blocks_explicit_git_add_of_artifact(
    git_repo: Path, tool_use, assert_blocks
) -> None:
    _write(git_repo, "game.sfc", b"rom-bytes")

    payload = tool_use("Bash", {"command": "git add game.sfc"})

    assert_blocks(HOOK, payload, "game.sfc")


def test_allows_git_add_of_ordinary_file(
    git_repo: Path, tool_use, assert_allows
) -> None:
    _write(git_repo, "README.md", b"# Title\n")

    payload = tool_use("Bash", {"command": "git add README.md"})

    assert_allows(HOOK, payload)


def test_block_message_follows_canonical_schema(
    git_repo: Path, tool_use, assert_blocks
) -> None:
    _stage(git_repo, "bios/scph1001.bin", b"bios-bytes")
    _stage(git_repo, "game.nds", b"rom-bytes")

    payload = tool_use("Bash", {"command": "git commit -m 'chore: add'"})

    _code, stderr = assert_blocks(HOOK, payload)
    assert validate_block_message(stderr) == []


def test_env_bypass_allows(git_repo: Path, tool_use, assert_allows) -> None:
    _stage(git_repo, "game.gba", b"rom-bytes")

    payload = tool_use("Bash", {"command": "git commit -m 'chore: add rom'"})

    assert_allows(HOOK, payload, env={"USER_SUPPLIED_ARTIFACT_DISABLE": "1"})


def test_registry_bypass_allows(
    git_repo: Path, tmp_path: Path, tool_use, assert_allows
) -> None:
    _stage(git_repo, "game.gba", b"rom-bytes")
    registry = tmp_path / "bypass.json"
    set_bypass(
        "user-supplied-artifact-guard",
        ttl_seconds=600,
        reason="test",
        state_path=registry,
    )

    payload = tool_use("Bash", {"command": "git commit -m 'chore: add rom'"})

    assert_allows(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(registry)})

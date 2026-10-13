from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from _helpers.raising import raising

ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = ROOT / "hooks" / "user-supplied-artifact-guard.py"
sys.path.insert(0, str(ROOT / "hooks"))
from _lib.bypass_writer import set_bypass  # noqa: E402
from _lib.output import validate_block_message  # noqa: E402

HOOK_NAME = "user-supplied-artifact-guard"
CONTENT_SHA256 = "ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73"
BYPASS_TTL_S = 120
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


@pytest.fixture()
def hook(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("_usag_mod", str(HOOK_PATH))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.delenv("USER_SUPPLIED_ARTIFACT_DISABLE", raising=False)
    monkeypatch.delenv("CLAUDE_DISABLED_HOOKS", raising=False)
    monkeypatch.setenv("CLAUDE_HOOK_AUDIT_DISABLE", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.setattr("_lib.bypass.STATE_PATH", Path(os.devnull))
    return module


@pytest.fixture()
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-q", str(repo)],
        check=True,
        env={**os.environ, **GIT_ENV},
        timeout=30,
    )
    monkeypatch.chdir(repo)
    return repo


def _stage(repo: Path, name: str, payload: bytes) -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    subprocess.run(["git", "add", "--", name], check=True, cwd=str(repo), timeout=30)


def _stdin_with(payload: object, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))


class VanishingPath(Path):
    def is_file(self) -> bool:
        return True

    def stat(self, *_args: object, **_kwargs: object) -> object:
        raise OSError("file vanished between checks")


def test_read_command_blocks_on_malformed_json(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert f"{HOOK_NAME} could not read its input" in capsys.readouterr().err


def test_read_command_blocks_on_non_dict_root(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert f"{HOOK_NAME} could not read its input" in capsys.readouterr().err


def test_read_command_blocks_on_non_dict_tool_input(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with({"tool_input": "scalar"}, monkeypatch)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert f"{HOOK_NAME} could not read its input" in capsys.readouterr().err


def test_read_command_blocks_when_command_non_string(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": 42}}, monkeypatch)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert "tool_input.command is not a string" in capsys.readouterr().err


def test_read_command_returns_string(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook._read_command()

    # Assert
    assert result == "git commit -m x"


def test_git_returns_empty_when_binary_missing(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    # Act
    result = hook._git(["status"])

    # Assert
    assert result == []


def test_git_returns_empty_on_non_zero_returncode(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)

    # Act
    result = hook._git(["diff", "--cached", "--name-only"])

    # Assert
    assert result == []


def test_staged_files_returns_empty_outside_git_repo(
    hook, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)

    # Act
    result = hook._staged_files()

    # Assert
    assert result == []


def test_explicit_add_paths_keeps_quoted_path_with_spaces_intact(hook) -> None:
    # Arrange
    command = "git add src/index.ts 'roms/My Game.sfc'"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == ["src/index.ts", "roms/My Game.sfc"]


def test_explicit_add_paths_falls_back_on_unbalanced_quotes(hook) -> None:
    # Arrange
    command = "git add roms/broken'.sfc"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == ["roms/broken'.sfc"]


def test_explicit_add_paths_sees_through_git_c_redirection(hook) -> None:
    # Arrange
    command = "git -C /repo add roms/game.sfc"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == ["roms/game.sfc"]


def test_commit_pattern_matches_git_c_redirection(hook) -> None:
    # Arrange
    text = "git -C /repo commit -m x"

    # Act
    result = hook.COMMIT_PATTERN.search(text)

    # Assert
    assert result is not None


def test_commit_pattern_ignores_the_word_commit_as_an_argument(hook) -> None:
    # Arrange
    text = "git log --grep commit"

    # Act
    result = hook.COMMIT_PATTERN.search(text)

    # Assert
    assert result is None


def test_explicit_add_paths_drops_flags_and_bulk_selectors(hook) -> None:
    # Arrange
    command = "git add -A . --update"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == []


def test_explicit_add_paths_ignores_other_git_subcommands(hook) -> None:
    # Arrange
    command = "git status && git log --oneline"

    # Act
    result = hook._explicit_add_paths(command)

    # Assert
    assert result == []


def test_repo_root_falls_back_to_cwd_outside_a_repo(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)

    # Act
    result = hook._repo_root()

    # Assert
    assert result.resolve() == tmp_path.resolve()


def test_repo_root_uses_git_toplevel_from_a_subdirectory(
    hook: ModuleType, git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    nested = git_repo / "packages" / "core"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    # Act
    result = hook._repo_root()

    # Assert
    assert result.resolve() == git_repo.resolve()


def test_manifest_claims_reads_digests_and_sizes(hook, tmp_path: Path) -> None:
    # Arrange
    digest = "a" * 64
    body = {"artifacts": [{"accepted": [{"size": 1024, "sha256": digest}]}]}
    (tmp_path / "artifacts.manifest.json").write_text(json.dumps(body))

    # Act
    digests, sizes = hook._manifest_claims(tmp_path)

    # Assert
    assert digests == {digest}
    assert sizes == {1024}


def test_manifest_claims_tolerates_unknown_shapes(hook, tmp_path: Path) -> None:
    # Arrange
    digest = "b" * 64
    body = {"nested": [{"deeper": {"sha256": digest.upper(), "size": 7}}]}
    (tmp_path / "artifacts.manifest.json").write_text(json.dumps(body))

    # Act
    digests, sizes = hook._manifest_claims(tmp_path)

    # Assert
    assert digests == {digest}
    assert sizes == {7}


def test_manifest_claims_ignores_malformed_digest_and_size(
    hook, tmp_path: Path
) -> None:
    # Arrange
    body = {"accepted": [{"sha256": "tooshort", "size": -1}]}
    (tmp_path / "artifacts.manifest.json").write_text(json.dumps(body))

    # Act
    digests, sizes = hook._manifest_claims(tmp_path)

    # Assert
    assert digests == set()
    assert sizes == set()


def test_manifest_claims_survives_invalid_json(hook, tmp_path: Path) -> None:
    # Arrange
    (tmp_path / "artifacts.manifest.json").write_text("{ not json")

    # Act
    digests, sizes = hook._manifest_claims(tmp_path)

    # Assert
    assert digests == set()
    assert sizes == set()


def test_manifest_claims_empty_when_no_manifest(hook, tmp_path: Path) -> None:
    # Arrange
    root = tmp_path

    # Act
    digests, sizes = hook._manifest_claims(root)

    # Assert
    assert digests == set()
    assert sizes == set()


def test_sha256_returns_none_for_unreadable_path(hook, tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "ghost.bin"

    # Act
    result = hook._sha256(path)

    # Assert
    assert result is None


def test_sha256_returns_the_known_digest(hook: ModuleType, tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "payload.bin"
    target.write_bytes(b"content")

    # Act
    result = hook._sha256(target)

    # Assert
    assert result == CONTENT_SHA256


def test_classify_returns_none_for_missing_path(hook, tmp_path: Path) -> None:
    # Arrange
    text = "ghost.bin"

    # Act
    result = hook._classify(text, tmp_path, set(), set())

    # Assert
    assert result is None


def test_classify_flags_artifact_extension(hook, tmp_path: Path) -> None:
    # Arrange
    (tmp_path / "game.gba").write_bytes(b"rom")

    # Act
    result = hook._classify("game.gba", tmp_path, set(), set())

    # Assert
    assert result == ".gba is a user-supplied artifact extension"


def test_classify_flags_manifest_digest(hook, tmp_path: Path) -> None:
    # Arrange
    body = b"content"
    (tmp_path / "blob.dat").write_bytes(body)
    digest = CONTENT_SHA256

    # Act
    result = hook._classify("blob.dat", tmp_path, {digest}, {len(body)})

    # Assert
    assert result == f"SHA-256 {digest[:12]} is declared in the artifacts manifest"


def test_classify_ignores_size_match_with_different_content(
    hook, tmp_path: Path
) -> None:
    # Arrange
    (tmp_path / "blob.dat").write_bytes(b"xxxxxxxx")

    # Act
    result = hook._classify("blob.dat", tmp_path, {"c" * 64}, {8})

    # Assert
    assert result is None


def test_classify_accepts_absolute_paths(hook, tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "game.nds"
    target.write_bytes(b"rom")

    # Act
    result = hook._classify(str(target), tmp_path, set(), set())

    # Assert
    assert result == ".nds is a user-supplied artifact extension"


def test_classify_resolves_paths_relative_to_the_working_directory(
    hook, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    workdir = tmp_path / "packages" / "emulator"
    workdir.mkdir(parents=True)
    (workdir / "game.gba").write_bytes(b"rom")
    monkeypatch.chdir(workdir)

    # Act
    result = hook._classify("game.gba", tmp_path, set(), set())

    # Assert
    assert result == ".gba is a user-supplied artifact extension"


def test_resolve_returns_none_for_missing_absolute_path(hook, tmp_path: Path) -> None:
    # Arrange
    name = str(tmp_path / "ghost.bin")

    # Act
    result = hook._resolve(name, tmp_path)

    # Assert
    assert result is None


def test_classify_survives_stat_failure_after_is_file(
    hook, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(hook, "Path", VanishingPath)

    # Act
    result = hook._classify(str(tmp_path / "blob.dat"), tmp_path, {"d" * 64}, {8})

    # Assert
    assert result is None


def test_git_returns_output_lines_inside_a_repo(
    hook: ModuleType, git_repo: Path
) -> None:
    # Arrange
    _stage(git_repo, "b.txt", b"b")
    _stage(git_repo, "a.txt", b"a")

    # Act
    result = hook._git(["diff", "--cached", "--name-only"])

    # Assert
    assert result == ["a.txt", "b.txt"]


def test_audit_noop_when_record_unavailable(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setattr(hook, "_audit_record", None)

    # Act
    hook._audit("git commit -m x", [("game.gba", "reason")])

    # Assert
    assert capsys.readouterr().err == ""


def test_audit_reports_a_record_exception_on_stderr(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    boom = raising(RuntimeError("audit explosion"))
    monkeypatch.setattr(hook, "_audit_record", boom)

    # Act
    hook._audit("git commit -m x", [("game.gba", "reason")])

    # Assert
    assert capsys.readouterr().err == (
        f"{HOOK_NAME}: audit log write failed: audit explosion\n"
    )


@pytest.fixture()
def staged_rom(hook: ModuleType, git_repo: Path, faker) -> Path:
    _stage(git_repo, "game.gba", faker.binary(length=64))
    return git_repo


def test_main_env_disable_allows_a_staged_artifact(
    hook: ModuleType,
    staged_rom: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setenv("USER_SUPPLIED_ARTIFACT_DISABLE", "1")
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_profile_gate_allows_a_staged_artifact(
    hook: ModuleType,
    staged_rom: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setenv("CLAUDE_DISABLED_HOOKS", HOOK_NAME)
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_file_bypass_allows_a_staged_artifact(
    hook: ModuleType,
    staged_rom: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    state = tmp_path / "bypass-state.json"
    set_bypass(HOOK_NAME, ttl_seconds=BYPASS_TTL_S, state_path=state)
    monkeypatch.setattr("_lib.bypass.STATE_PATH", state)
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_ignores_an_unrelated_command_with_an_artifact_staged(
    hook: ModuleType,
    staged_rom: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "ls -la"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_allows_a_commit_when_nothing_is_staged(
    hook: ModuleType,
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_allows_when_no_candidate_is_an_artifact(
    hook: ModuleType,
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stage(git_repo, "notes.md", b"# notes\n")
    _stdin_with(
        {"tool_input": {"command": "git add ghost.bin && git commit -m x"}}, monkeypatch
    )

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_deduplicates_repeated_candidates(
    hook: ModuleType,
    staged_rom: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with(
        {"tool_input": {"command": "git add game.gba && git commit -m x"}}, monkeypatch
    )

    # Act
    result = hook.main()

    # Assert
    stderr = capsys.readouterr().err
    assert result == 2
    assert stderr.count("game.gba:") == 1
    assert "1 user-supplied artifact(s)" in stderr


def test_main_blocks_and_renders_canonical_message(
    hook: ModuleType,
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    faker,
) -> None:
    # Arrange
    _stage(git_repo, "game.z64", faker.binary(length=64))
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    stderr = capsys.readouterr().err
    assert result == 2
    assert "game.z64: .z64 is a user-supplied artifact extension" in stderr
    assert validate_block_message(stderr) == []

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from _helpers.raising import raising

ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = ROOT / "hooks" / "user-supplied-artifact-guard.py"
sys.path.insert(0, str(ROOT / "hooks"))
from _lib.output import validate_block_message  # noqa: E402


@pytest.fixture()
def hook(monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("_usag_mod", str(HOOK_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.delenv("USER_SUPPLIED_ARTIFACT_DISABLE", raising=False)
    monkeypatch.delenv("CLAUDE_BYPASS_STATE", raising=False)
    return module


def _stdin_with(payload: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def boom(*_args: object, **_kwargs: object) -> object:
    raise OSError("simulated")


class VanishingPath(Path):
    def is_file(self) -> bool:
        return True

    def stat(self, *_args: object, **_kwargs: object) -> object:
        raise OSError("file vanished between checks")


def test_read_command_returns_empty_on_malformed_json(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))

    # Act
    result = hook._read_command()

    # Assert
    assert result == ""


def test_read_command_returns_empty_on_non_dict_root(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))

    # Act
    result = hook._read_command()

    # Assert
    assert result == ""


def test_read_command_returns_empty_on_non_dict_tool_input(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _stdin_with({"tool_input": "scalar"}, monkeypatch)

    # Act
    result = hook._read_command()

    # Assert
    assert result == ""


def test_read_command_returns_empty_when_command_non_string(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": 42}}, monkeypatch)

    # Act
    result = hook._read_command()

    # Assert
    assert result == ""


def test_read_command_returns_string(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook._read_command()

    # Assert
    assert result == "git commit -m x"


def test_git_returns_empty_when_binary_missing(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(hook.subprocess, "run", boom)

    # Act
    result = hook._git(["status"])

    # Assert
    assert result == []


def test_git_returns_empty_on_non_zero_returncode(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(
        hook.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(stdout="ignored\n", returncode=128),
    )

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


def test_repo_root_falls_back_to_cwd(
    hook, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(hook, "_git", lambda _args: [])
    monkeypatch.chdir(tmp_path)

    # Act
    result = hook._repo_root()

    # Assert
    assert result == Path.cwd()


def test_repo_root_uses_git_toplevel(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook, "_git", lambda _args: ["/repo/root"])

    # Act
    result = hook._repo_root()

    # Assert
    assert result == Path("/repo/root")


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


def test_sha256_matches_hashlib(hook, tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "payload.bin"
    target.write_bytes(b"content")

    # Act
    result = hook._sha256(target)

    # Assert
    assert result == hashlib.sha256(b"content").hexdigest()


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
    assert result is not None
    assert ".gba" in result


def test_classify_flags_manifest_digest(hook, tmp_path: Path) -> None:
    # Arrange
    body = b"artifact"
    (tmp_path / "blob.dat").write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()

    # Act
    result = hook._classify("blob.dat", tmp_path, {digest}, {len(body)})

    # Assert
    assert result is not None
    assert "manifest" in result


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
    assert result is not None


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
    assert result is not None


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
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(ROOT)

    # Act
    result = hook._git(["rev-parse", "--show-toplevel"])

    # Assert
    assert result == [str(ROOT)]


def test_audit_noop_when_record_unavailable(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(hook, "_audit_record", None)

    # Act
    result = hook._audit("git commit -m x", [("game.gba", "reason")])

    # Assert
    assert result is None


def test_audit_swallows_record_exception(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    boom = raising(RuntimeError("audit explosion"))
    monkeypatch.setattr(hook, "_audit_record", boom)

    # Act
    result = hook._audit("git commit -m x", [("game.gba", "reason")])

    # Assert
    assert result is None


def test_main_env_disable_short_circuits(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("USER_SUPPLIED_ARTIFACT_DISABLE", "1")

    # Act
    result = hook.main()

    # Assert
    assert result == 0


def test_main_profile_gate_short_circuits(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(hook, "should_run", lambda _name: False)

    # Act
    result = hook.main()

    # Assert
    assert result == 0


def test_main_file_bypass_short_circuits(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook, "is_bypassed", lambda _name: True)

    # Act
    result = hook.main()

    # Assert
    assert result == 0


def test_main_returns_zero_on_unrelated_command(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "ls -la"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0


def test_main_allows_when_nothing_staged(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)
    monkeypatch.setattr(hook, "_staged_files", lambda: [])

    # Act
    result = hook.main()

    # Assert
    assert result == 0


def test_main_allows_when_no_candidate_is_an_artifact(
    hook, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    (tmp_path / "notes.md").write_bytes(b"# notes\n")
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)
    monkeypatch.setattr(hook, "_staged_files", lambda: ["notes.md", "ghost.bin"])
    monkeypatch.setattr(hook, "_repo_root", lambda: tmp_path)

    # Act
    result = hook.main()

    # Assert
    assert result == 0


def test_main_deduplicates_repeated_candidates(
    hook,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    (tmp_path / "game.gba").write_bytes(b"rom")
    _stdin_with(
        {"tool_input": {"command": "git add game.gba && git commit -m x"}}, monkeypatch
    )
    monkeypatch.setattr(hook, "_staged_files", lambda: ["game.gba"])
    monkeypatch.setattr(hook, "_repo_root", lambda: tmp_path)

    # Act
    result = hook.main()

    # Assert
    captured = capsys.readouterr()
    assert result == 2
    assert captured.err.count("game.gba:") == 1
    assert "1 user-supplied artifact(s)" in captured.err


def test_main_blocks_and_renders_canonical_message(
    hook,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    (tmp_path / "game.z64").write_bytes(b"rom")
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)
    monkeypatch.setattr(hook, "_staged_files", lambda: ["game.z64"])
    monkeypatch.setattr(hook, "_repo_root", lambda: tmp_path)

    # Act
    result = hook.main()

    # Assert
    captured = capsys.readouterr()
    assert result == 2
    assert validate_block_message(captured.err) == []

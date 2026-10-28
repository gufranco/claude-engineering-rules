from __future__ import annotations
from pathlib import Path
import pytest
from _stop_format_typecheck_helpers import _load, _make_recording_stub, _run
from _lib.bypass_writer import set_bypass  # noqa: E402


def test_empty_batch_file_is_consumed_without_output(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    batch.write_text("", encoding="utf-8")

    # Act
    result = _run(batch)

    # Assert
    assert (result.returncode, result.stdout, batch.exists()) == (0, "", False)


def test_missing_batch_file_produces_no_output(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"

    # Act
    result = _run(batch)

    # Assert
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_clears_batch_file_after_run(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "f.py"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_recording_stub(bin_dir, "ruff", tmp_path / "calls.json")

    # Act
    result = _run(batch, bin_dir=bin_dir)

    # Assert
    assert (result.returncode, batch.exists()) == (0, False)


def test_skips_missing_files(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{tmp_path}/missing.ts\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)

    # Act
    result = _run(batch, bin_dir=bin_dir)

    # Assert
    assert result.returncode == 0
    assert log.exists() is False


def test_env_disable_short_circuits(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)

    # Act
    result = _run(batch, bin_dir=bin_dir, env={"STOP_FORMAT_DISABLE": "1"})

    # Assert
    assert result.returncode == 0
    assert log.exists() is False
    assert batch.read_text(encoding="utf-8") != ""


def test_file_bypass_short_circuits(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    state = tmp_path / "state.json"
    set_bypass("stop-format-typecheck", ttl_seconds=120, state_path=state)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)

    # Act
    result = _run(batch, bin_dir=bin_dir, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert result.returncode == 0
    assert log.exists() is False


def test_profile_disable_short_circuits(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)

    # Act
    result = _run(
        batch,
        bin_dir=bin_dir,
        env={"CLAUDE_DISABLED_HOOKS": "stop-format-typecheck"},
    )

    # Assert
    assert result.returncode == 0
    assert log.exists() is False


def test_run_quietly_reports_a_tool_that_cannot_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    module = _load("_sft_mod")
    missing = str(tmp_path / "never-installed")

    # Act
    module._run_quietly([missing])

    # Assert
    assert capsys.readouterr().err.startswith(
        f"stop-format-typecheck: {missing} failed: "
    )


def test_format_with_skips_a_tool_missing_from_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    module = _load("_sft_mod2")
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    # Act
    module._format_with("never-installed", "--write", str(tmp_path / "x"))

    # Assert
    assert capsys.readouterr().err == ""


def test_each_session_has_its_own_batch_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    module = _load("_sft_mod5")
    monkeypatch.delenv("CLAUDE_FORMATTER_BATCH", raising=False)
    cache = Path.home() / ".claude" / "cache"

    # Act
    paths = [module.batch_path("session-a"), module.batch_path("session-b")]

    # Assert
    assert paths == [
        cache / "edit-batch-session-a.txt",
        cache / "edit-batch-session-b.txt",
    ]


def test_an_unreadable_payload_is_reported_and_the_batch_still_runs(
    tmp_path: Path,
) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    batch.write_text("", encoding="utf-8")

    # Act
    result = _run(batch, stdin="not json")

    # Assert
    assert result.returncode == 0
    assert result.stderr.startswith("stop-format-typecheck: unreadable payload: ")
    assert batch.exists() is False


def test_python_files_are_left_alone_without_ruff_or_black(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    module = _load("_sft_mod_py")
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    source = tmp_path / "loose.py"
    source.write_text("x=1\n", encoding="utf-8")

    # Act
    module._format_python([str(source)])

    # Assert
    assert (source.read_text(encoding="utf-8"), capsys.readouterr().err) == (
        "x=1\n",
        "",
    )

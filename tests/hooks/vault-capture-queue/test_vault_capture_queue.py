from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "hooks" / "vault-capture-queue.py"


def load():
    spec = importlib.util.spec_from_file_location("vault_capture_queue", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["vault_capture_queue"] = module
    spec.loader.exec_module(module)
    return module


CORRECTION_LINE = "the user said: no, not that, use the other one"
DISCOVERY_LINES = [
    "turns out the root cause was the shell, not the tool",
    "the check reports success silently even when nothing ran",
]
QUIET_LINES = ["ran the tests", "everything passed", "committed the change"]


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "wiki" / "concepts").mkdir(parents=True)
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    return repo


@pytest.fixture
def transcript(tmp_path: Path):
    def _write(lines: list[str]) -> Path:
        path = tmp_path / "transcript.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return _write


@pytest.fixture
def no_subprocess(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the capture queue must not start a process")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("os.system", forbidden)


def stop_payload(cwd, session: str, transcript_path) -> str:
    return json.dumps(
        {
            "hook_event_name": "Stop",
            "cwd": str(cwd),
            "session_id": session,
            "transcript_path": str(transcript_path) if transcript_path else "",
        }
    )


def run(
    monkeypatch,
    tmp_path,
    vault_path,
    cwd,
    transcript_path=None,
    session="sess-default",
    env=None,
    stdin=None,
):
    module = load()
    monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault_path))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session)
    monkeypatch.delenv("VAULT_CAPTURE_QUEUE_DISABLE", raising=False)
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    payload = stop_payload(cwd, session, transcript_path) if stdin is None else stdin
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return module.run()


def queued(vault: Path) -> list[dict]:
    path = vault / ".claude-runs" / "capture-queue.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_queues_a_capture_when_the_user_corrected_something(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript([CORRECTION_LINE])

    # Act
    code = run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    assert code == 0
    assert len(queued(vault)) == 1


def test_queues_a_capture_when_the_turn_produced_a_discovery(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript(DISCOVERY_LINES)

    # Act
    code = run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    assert code == 0
    assert len(queued(vault)) == 1


def test_stays_quiet_on_an_ordinary_turn(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript(QUIET_LINES)

    # Act
    code = run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    assert code == 0
    assert queued(vault) == []


def test_a_single_discovery_marker_is_not_enough(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript([DISCOVERY_LINES[0]])

    # Act
    run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    assert queued(vault) == []


def test_the_entry_carries_what_the_next_session_needs(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript([CORRECTION_LINE])

    # Act
    run(monkeypatch, tmp_path, vault, project, path, session="sess-fields")

    # Assert
    entries = queued(vault)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["status"] == "pending"
    assert entry["cwd"] == str(project)
    assert entry["transcript"] == str(path)
    assert entry["session"] == "sess-fields"
    assert entry["signals"] == ["correction:1"]
    assert entry["ts"] > 0


def test_a_second_turn_inside_the_cooldown_does_not_queue_again(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript([CORRECTION_LINE])
    run(monkeypatch, tmp_path, vault, project, path, session="sess-cooldown")

    # Act
    run(monkeypatch, tmp_path, vault, project, path, session="sess-cooldown")

    # Assert
    assert len(queued(vault)) == 1


def test_a_different_session_is_not_held_by_the_cooldown(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript([CORRECTION_LINE])
    run(monkeypatch, tmp_path, vault, project, path, session="sess-one")

    # Act
    run(monkeypatch, tmp_path, vault, project, path, session="sess-two")

    # Assert
    assert len(queued(vault)) == 2


def test_it_appends_rather_than_replacing_the_queue(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    runs = vault / ".claude-runs"
    runs.mkdir(parents=True)
    existing = json.dumps({"status": "pending", "session": "earlier"})
    (runs / "capture-queue.jsonl").write_text(existing + "\n", encoding="utf-8")
    path = transcript([CORRECTION_LINE])

    # Act
    run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    entries = queued(vault)
    assert len(entries) == 2
    assert entries[0]["session"] == "earlier"


def test_it_writes_only_inside_the_run_directory(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    before = {p for p in vault.rglob("*") if p.is_file()}
    path = transcript([CORRECTION_LINE])

    # Act
    run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    written = {p for p in vault.rglob("*") if p.is_file()} - before
    assert written == {vault / ".claude-runs" / "capture-queue.jsonl"}


def test_it_is_inert_when_switched_off(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript([CORRECTION_LINE])

    # Act
    code = run(
        monkeypatch,
        tmp_path,
        vault,
        project,
        path,
        env={"VAULT_CAPTURE_QUEUE_DISABLE": "1"},
    )

    # Assert
    assert code == 0
    assert queued(vault) == []


def test_it_is_inert_without_a_vault(
    monkeypatch, tmp_path, project, transcript, no_subprocess
):
    # Arrange
    path = transcript([CORRECTION_LINE])
    missing = tmp_path / "no-vault"

    # Act
    code = run(monkeypatch, tmp_path, missing, project, path)

    # Assert
    assert code == 0
    assert (missing / ".claude-runs").exists() is False


def test_it_skips_a_session_spent_editing_the_vault(
    monkeypatch, tmp_path, vault, transcript, no_subprocess
):
    # Arrange
    path = transcript([CORRECTION_LINE])

    # Act
    run(monkeypatch, tmp_path, vault, vault, path)

    # Assert
    assert queued(vault) == []


def test_a_missing_transcript_is_tolerated(
    monkeypatch, tmp_path, vault, project, no_subprocess
):
    # Arrange
    transcript_path = tmp_path / "absent.jsonl"

    # Act
    code = run(monkeypatch, tmp_path, vault, project, transcript_path)

    # Assert
    assert code == 0
    assert queued(vault) == []


def test_malformed_stdin_is_tolerated(
    monkeypatch, tmp_path, vault, project, no_subprocess
):
    # Arrange
    stdin = "not json at all"

    # Act
    code = run(monkeypatch, tmp_path, vault, project, stdin=stdin)

    # Assert
    assert code == 0
    assert queued(vault) == []


def test_portuguese_corrections_count_as_signals(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript(["na verdade nao e isso, tome cuidado com isso"])

    # Act
    run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    assert len(queued(vault)) == 1


def test_an_unreadable_queue_directory_does_not_fail_the_turn(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    blocker = vault / ".claude-runs"
    blocker.write_text("not a directory", encoding="utf-8")
    path = transcript([CORRECTION_LINE])

    # Act
    code = run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    assert code == 0
    assert blocker.read_text(encoding="utf-8") == "not a directory"


def test_a_long_transcript_is_read_from_its_tail(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript(["x" * 300 * 1024, CORRECTION_LINE])

    # Act
    code = run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    assert (code, len(queued(vault))) == (0, 1)


def test_the_session_comes_from_the_environment_when_the_payload_lacks_it(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    # Arrange
    path = transcript([CORRECTION_LINE])
    payload = json.dumps({"cwd": str(project), "transcript_path": str(path)})

    # Act
    code = run(
        monkeypatch, tmp_path, vault, project, path, session="env-sess", stdin=payload
    )

    # Assert
    assert (code, queued(vault)[0]["session"]) == (0, "env-sess")


def test_an_unreadable_transcript_is_reported_and_skipped(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess, capsys
):
    # Arrange
    path = transcript([CORRECTION_LINE])
    Path(path).chmod(0)

    # Act
    code = run(monkeypatch, tmp_path, vault, project, path)

    # Assert
    assert (code, queued(vault)) == (0, [])
    assert capsys.readouterr().err.startswith("vault-capture-queue: capture skipped: ")

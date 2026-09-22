"""Coverage for the end-of-turn capture queue.

The hook decides whether a turn produced something worth keeping and, when it
did, appends one line to a queue the next session drains. It deliberately does
not write notes and does not start anything: a process cannot tell a durable
lesson from an aside, and an unattended writer holding that judgement is the
failure mode this design removes.

So the load-bearing tests are the negative ones. It must stay silent on an
ordinary turn, it must never launch a subprocess, and it must never touch the
vault outside its own run directory.
"""

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
    """Fail loudly if the hook ever tries to start anything."""

    def forbidden(*args, **kwargs):
        raise AssertionError("the capture queue must not start a process")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("os.system", forbidden)


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
    payload = (
        stdin
        if stdin is not None
        else json.dumps(
            {
                "hook_event_name": "Stop",
                "cwd": str(cwd),
                "session_id": session,
                "transcript_path": str(transcript_path) if transcript_path else "",
            }
        )
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return module.main()


def queued(vault: Path) -> list[dict]:
    path = vault / ".claude-runs" / "capture-queue.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_queues_a_capture_when_the_user_corrected_something(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    path = transcript([CORRECTION_LINE])

    code = run(monkeypatch, tmp_path, vault, project, path)

    assert code == 0
    assert len(queued(vault)) == 1


def test_queues_a_capture_when_the_turn_produced_a_discovery(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    path = transcript(DISCOVERY_LINES)

    code = run(monkeypatch, tmp_path, vault, project, path)

    assert code == 0
    assert len(queued(vault)) == 1


def test_stays_quiet_on_an_ordinary_turn(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    path = transcript(QUIET_LINES)

    code = run(monkeypatch, tmp_path, vault, project, path)

    assert code == 0
    assert queued(vault) == []


def test_a_single_discovery_marker_is_not_enough(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    path = transcript([DISCOVERY_LINES[0]])

    run(monkeypatch, tmp_path, vault, project, path)

    assert queued(vault) == []


def test_the_entry_carries_what_the_next_session_needs(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    path = transcript([CORRECTION_LINE])

    run(monkeypatch, tmp_path, vault, project, path, session="sess-fields")

    entry = queued(vault)[0]
    assert entry["status"] == "pending"
    assert entry["cwd"] == str(project)
    assert entry["transcript"] == str(path)
    assert entry["session"] == "sess-fields"
    assert entry["signals"]
    assert entry["ts"]


def test_a_second_turn_inside_the_cooldown_does_not_queue_again(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    path = transcript([CORRECTION_LINE])

    run(monkeypatch, tmp_path, vault, project, path, session="sess-cooldown")
    run(monkeypatch, tmp_path, vault, project, path, session="sess-cooldown")

    assert len(queued(vault)) == 1


def test_a_different_session_is_not_held_by_the_cooldown(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    path = transcript([CORRECTION_LINE])

    run(monkeypatch, tmp_path, vault, project, path, session="sess-one")
    run(monkeypatch, tmp_path, vault, project, path, session="sess-two")

    assert len(queued(vault)) == 2


def test_it_appends_rather_than_replacing_the_queue(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    runs = vault / ".claude-runs"
    runs.mkdir(parents=True)
    existing = json.dumps({"status": "pending", "session": "earlier"})
    (runs / "capture-queue.jsonl").write_text(existing + "\n", encoding="utf-8")
    path = transcript([CORRECTION_LINE])

    run(monkeypatch, tmp_path, vault, project, path)

    entries = queued(vault)
    assert len(entries) == 2
    assert entries[0]["session"] == "earlier"


def test_it_writes_only_inside_the_run_directory(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    before = {p for p in vault.rglob("*") if p.is_file()}
    path = transcript([CORRECTION_LINE])

    run(monkeypatch, tmp_path, vault, project, path)

    written = {p for p in vault.rglob("*") if p.is_file()} - before
    assert written == {vault / ".claude-runs" / "capture-queue.jsonl"}


def test_it_is_inert_when_switched_off(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    path = transcript([CORRECTION_LINE])

    code = run(
        monkeypatch,
        tmp_path,
        vault,
        project,
        path,
        env={"VAULT_CAPTURE_QUEUE_DISABLE": "1"},
    )

    assert code == 0
    assert queued(vault) == []


def test_it_is_inert_without_a_vault(
    monkeypatch, tmp_path, project, transcript, no_subprocess
):
    path = transcript([CORRECTION_LINE])
    missing = tmp_path / "no-vault"

    code = run(monkeypatch, tmp_path, missing, project, path)

    assert code == 0
    assert not (missing / ".claude-runs").exists()


def test_it_skips_a_session_spent_editing_the_vault(
    monkeypatch, tmp_path, vault, transcript, no_subprocess
):
    path = transcript([CORRECTION_LINE])

    run(monkeypatch, tmp_path, vault, vault, path)

    assert queued(vault) == []


def test_a_missing_transcript_is_tolerated(
    monkeypatch, tmp_path, vault, project, no_subprocess
):
    code = run(monkeypatch, tmp_path, vault, project, tmp_path / "absent.jsonl")

    assert code == 0
    assert queued(vault) == []


def test_malformed_stdin_is_tolerated(
    monkeypatch, tmp_path, vault, project, no_subprocess
):
    code = run(monkeypatch, tmp_path, vault, project, stdin="not json at all")

    assert code == 0
    assert queued(vault) == []


def test_portuguese_corrections_count_as_signals(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    path = transcript(["na verdade nao e isso, tome cuidado com isso"])

    run(monkeypatch, tmp_path, vault, project, path)

    assert len(queued(vault)) == 1


def test_an_unreadable_queue_directory_does_not_fail_the_turn(
    monkeypatch, tmp_path, vault, project, transcript, no_subprocess
):
    (vault / ".claude-runs").write_text("not a directory", encoding="utf-8")
    path = transcript([CORRECTION_LINE])

    assert run(monkeypatch, tmp_path, vault, project, path) == 0

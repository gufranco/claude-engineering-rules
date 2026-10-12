from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[3] / "hooks" / "vault-context-loader.py"

INDEX = """---
date: 2026-08-18
type: index
tags: [index]
ai-first: true
---

## For future agent

Catalog of the vault.

## Concepts

- [[Postgres Indexing]] - how partial indexes narrow a scan
"""


def load():
    spec = importlib.util.spec_from_file_location("vault_context_loader", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["vault_context_loader"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "index.md").write_text(INDEX)
    return root


def run(monkeypatch, vault_path, stdin: str = '{"hook_event_name": "SessionStart"}'):
    module = load()
    monkeypatch.delenv("VAULT_CONTEXT_DISABLE", raising=False)
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault_path))
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)
    code = module.main()
    return code, captured.getvalue()


def test_emits_the_index_as_additional_context(monkeypatch, vault):
    # Arrange
    vault_input = vault

    # Act
    code, out = run(monkeypatch, vault_input)

    # Assert
    assert code == 0
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Postgres Indexing" in payload["hookSpecificOutput"]["additionalContext"]


def test_names_the_vault_path_so_the_agent_can_resolve_it(monkeypatch, vault):
    # Arrange
    vault_input = vault

    # Act
    _code, out = run(monkeypatch, vault_input)

    # Assert
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert str(vault) in context


def test_is_silent_when_the_vault_does_not_exist(monkeypatch, tmp_path):
    # Arrange
    vault_path = tmp_path / "absent"

    # Act
    code, out = run(monkeypatch, vault_path)

    # Assert
    assert code == 0
    assert out == ""


def test_is_silent_when_the_index_is_missing(monkeypatch, tmp_path):
    # Arrange
    root = tmp_path / "vault"
    root.mkdir()

    # Act
    code, out = run(monkeypatch, root)

    # Assert
    assert code == 0
    assert out == ""


def test_truncates_a_large_index(monkeypatch, tmp_path):
    # Arrange
    root = tmp_path / "vault"
    root.mkdir()
    (root / "index.md").write_text(
        INDEX + "\n" + ("- [[Filler]] padding line\n" * 5000)
    )

    # Act
    _code, out = run(monkeypatch, root)

    # Assert
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert len(context) < 20000
    assert "truncated" in context.lower()


def test_bypass_env_silences_it(monkeypatch, vault):
    # Arrange
    module = load()
    monkeypatch.setenv("VAULT_CONTEXT_DISABLE", "1")
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault))
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    # Act
    result = module.main()

    # Assert
    assert result == 0
    assert captured.getvalue() == ""


def test_malformed_stdin_is_tolerated(monkeypatch, vault):
    # Arrange
    stdin = "not json"

    # Act
    code, out = run(monkeypatch, vault, stdin=stdin)

    # Assert
    assert code == 0
    assert out == ""


def test_an_unreadable_index_is_tolerated(monkeypatch, tmp_path):
    # Arrange
    root = tmp_path / "vault"
    root.mkdir()
    (root / "index.md").mkdir()

    # Act
    code, out = run(monkeypatch, root)

    # Assert
    assert code == 0
    assert out == ""


def queue(vault: Path, entries: list[dict]) -> None:
    runs = vault / ".claude-runs"
    runs.mkdir(exist_ok=True)
    body = "\n".join(json.dumps(entry) for entry in entries)
    (runs / "capture-queue.jsonl").write_text(body + "\n", encoding="utf-8")


def pending_entry(session: str = "s1", cwd: str = "/tmp/project") -> dict:
    return {
        "ts": 1758500000,
        "status": "pending",
        "session": session,
        "cwd": cwd,
        "transcript": "/tmp/t.jsonl",
        "signals": ["correction:1"],
    }


def test_surfaces_a_pending_capture_so_the_session_files_it(monkeypatch, vault):
    # Arrange
    queue(vault, [pending_entry()])

    # Act
    _code, out = run(monkeypatch, vault)

    # Assert
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "1 pending capture" in context
    assert "/tmp/project" in context


def test_counts_several_pending_captures(monkeypatch, vault):
    # Arrange
    queue(vault, [pending_entry("s1"), pending_entry("s2"), pending_entry("s3")])

    # Act
    _code, out = run(monkeypatch, vault)

    # Assert
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "3 pending captures" in context


def test_says_nothing_when_the_queue_is_empty(monkeypatch, vault):
    # Arrange
    queue(vault, [])

    # Act
    _code, out = run(monkeypatch, vault)

    # Assert
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "pending capture" not in context


def test_says_nothing_when_there_is_no_queue(monkeypatch, vault):
    # Arrange
    vault_input = vault

    # Act
    _code, out = run(monkeypatch, vault_input)

    # Assert
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "pending capture" not in context


def test_ignores_entries_already_filed(monkeypatch, vault):
    # Arrange
    done = {**pending_entry("s1"), "status": "filed"}
    queue(vault, [done, pending_entry("s2")])

    # Act
    _code, out = run(monkeypatch, vault)

    # Assert
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "1 pending capture" in context


def test_a_corrupt_queue_line_does_not_break_the_session(monkeypatch, vault):
    # Arrange
    runs = vault / ".claude-runs"
    runs.mkdir(exist_ok=True)
    (runs / "capture-queue.jsonl").write_text(
        "not json\n" + json.dumps(pending_entry()) + "\n", encoding="utf-8"
    )

    # Act
    code, out = run(monkeypatch, vault)

    # Assert
    assert code == 0
    assert (
        "1 pending capture"
        in json.loads(out)["hookSpecificOutput"]["additionalContext"]
    )


def test_an_unreadable_queue_does_not_break_the_session(monkeypatch, vault):
    # Arrange
    (vault / ".claude-runs").write_text("not a directory", encoding="utf-8")

    # Act
    code, out = run(monkeypatch, vault)

    # Assert
    assert code == 0
    assert (
        "pending capture"
        not in json.loads(out)["hookSpecificOutput"]["additionalContext"]
    )

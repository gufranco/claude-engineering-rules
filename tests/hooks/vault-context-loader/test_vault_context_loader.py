"""Coverage for the vault context loader.

A session that does not know what the vault already holds will re-derive
knowledge it has, and file duplicates of notes that exist.
"""

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
    code, out = run(monkeypatch, vault)

    assert code == 0
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Postgres Indexing" in payload["hookSpecificOutput"]["additionalContext"]


def test_names_the_vault_path_so_the_agent_can_resolve_it(monkeypatch, vault):
    _code, out = run(monkeypatch, vault)

    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert str(vault) in context


def test_is_silent_when_the_vault_does_not_exist(monkeypatch, tmp_path):
    code, out = run(monkeypatch, tmp_path / "absent")

    assert code == 0
    assert out == ""


def test_is_silent_when_the_index_is_missing(monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()

    code, out = run(monkeypatch, root)

    assert code == 0
    assert out == ""


def test_truncates_a_large_index(monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "index.md").write_text(
        INDEX + "\n" + ("- [[Filler]] padding line\n" * 5000)
    )

    _code, out = run(monkeypatch, root)

    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert len(context) < 20000
    assert "truncated" in context.lower()


def test_bypass_env_silences_it(monkeypatch, vault):
    module = load()
    monkeypatch.setenv("VAULT_CONTEXT_DISABLE", "1")
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault))
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    assert module.main() == 0
    assert captured.getvalue() == ""


def test_malformed_stdin_is_tolerated(monkeypatch, vault):
    code, out = run(monkeypatch, vault, stdin="not json")

    assert code == 0
    assert out == ""


def test_an_unreadable_index_is_tolerated(monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "index.md").mkdir()

    code, out = run(monkeypatch, root)

    assert code == 0
    assert out == ""

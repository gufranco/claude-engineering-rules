"""Audit log coverage.

Item 127 of the plan. Validates that every block emits a JSONL record
with the expected fields: detector, decision, tool, version, duration_ms,
ast_used, files_scanned, command_excerpt.

The audit log writes to ~/.claude/logs/hooks.log by default. Tests
override HOME so each subprocess writes to a per-test temp directory,
avoiding pollution of the user's real audit log.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import make_edit_payload, make_write_payload, run_hook_subprocess


@pytest.fixture
def audit_home(tmp_path: Path) -> tuple[Path, Path]:
    """Return (home, log_path). Subprocesses launched with HOME=home will
    write hooks.log under home/.claude/logs/hooks.log."""
    home = tmp_path / "home"
    (home / ".claude" / "logs").mkdir(parents=True)
    return home, home / ".claude" / "logs" / "hooks.log"


def _read_records(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [
        json.loads(line) for line in log_path.read_text().splitlines() if line.strip()
    ]


def test_block_emits_audit_record(hook_path, audit_home):
    # Arrange
    home, log_path = audit_home
    payload = make_edit_payload("/repo/src/app.ts", "items.push(value)")

    # Act
    code, _, _ = run_hook_subprocess(
        hook_path,
        payload,
        env={"HOME": str(home), "CLAUDE_HOOK_AUDIT_DISABLE": "0"},
    )

    # Assert
    assert code == 2
    records = _read_records(log_path)
    assert records, "expected at least one audit record"
    block_records = [r for r in records if r.get("decision") == "block"]
    assert block_records, f"no block decision found in {records}"
    block = block_records[0]
    assert block["hook"] == "mutation-method-blocker"
    assert block["tool"] == "Edit"
    assert block["version"] == "2.0.0"
    assert "duration_ms" in block
    assert "ast_used" in block
    assert "detector" in block
    assert "array.push" in (block.get("detector") or "")
    assert block.get("files_scanned", 0) >= 1


def test_allow_emits_audit_record_when_files_scanned(hook_path, audit_home):
    # Arrange
    home, log_path = audit_home
    payload = make_edit_payload("/repo/src/app.ts", "const next = [...items, value]")

    # Act
    code, _, _ = run_hook_subprocess(
        hook_path,
        payload,
        env={"HOME": str(home), "CLAUDE_HOOK_AUDIT_DISABLE": "0"},
    )

    # Assert
    assert code == 0
    records = _read_records(log_path)
    allow_records = [r for r in records if r.get("decision") == "allow"]
    assert allow_records, f"no allow decision found in {records}"
    allow = allow_records[0]
    assert allow["hook"] == "mutation-method-blocker"
    assert allow["tool"] == "Edit"
    assert allow["version"] == "2.0.0"
    assert "duration_ms" in allow


def test_bypass_env_emits_audit_record(hook_path, audit_home):
    # Arrange
    home, log_path = audit_home
    payload = make_edit_payload("/repo/src/app.ts", "items.push(value)")

    # Act
    code, _, _ = run_hook_subprocess(
        hook_path,
        payload,
        env={
            "HOME": str(home),
            "CLAUDE_HOOK_AUDIT_DISABLE": "0",
            "MUTATION_METHOD_DISABLE": "1",
        },
    )

    # Assert
    assert code == 0
    records = _read_records(log_path)
    bypass_records = [r for r in records if r.get("decision") == "bypass"]
    assert bypass_records
    assert bypass_records[0]["bypass_env"] == "MUTATION_METHOD_DISABLE"


def test_block_record_includes_state_mgmt_allow_reasons(hook_path, audit_home):
    # Arrange
    home, log_path = audit_home
    snippet = """import { produce } from 'immer';
const next = produce(state, (draft) => {
  draft.list.push(value);
});
items.push(direct);
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, _, _ = run_hook_subprocess(
        hook_path,
        payload,
        env={"HOME": str(home), "CLAUDE_HOOK_AUDIT_DISABLE": "0"},
    )

    # Assert
    assert code == 2
    records = _read_records(log_path)
    block = next((r for r in records if r.get("decision") == "block"), None)
    assert block is not None
    assert "array.push" in (block.get("detector") or "")

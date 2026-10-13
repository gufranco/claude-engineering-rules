from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _kng_support import (
    GOOD,
    HOOK,
    note,
)


def test_bypass_env_allows_everything(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Bare.md"), "content": "nothing here"},
    )

    # Act
    result = run_hook(HOOK, payload, env={**env, "KNOWLEDGE_NOTE_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_allows_when_the_vault_does_not_exist(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": str(tmp_path / "x.md"), "content": "nothing here"}
    )

    # Act
    result = run_hook(
        HOOK, payload, env={"SECOND_BRAIN_VAULT": str(tmp_path / "missing")}
    )

    # Assert
    assert_allowed(result)


def test_allows_unrelated_tool(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use("Read", {"file_path": note(vault, "wiki/concepts/Idea.md")})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_payload_without_a_file_path(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use("Write", {"content": GOOD})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_frontmatter_with_a_yaml_list(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD.replace("tags: [concept]", "tags:\n  - concept\n  - idea")
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Listed.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_blocks_wikilink_to_a_template(tool_use, run_hook, vault, env):
    # Arrange
    (vault / "templates/entity.md").write_text("template body")
    content = GOOD + "\nSee [[entity]] for the shape.\n"
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Shape.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN004")


def test_caps_the_number_of_reported_findings(tool_use, run_hook, vault, env):
    # Arrange
    noise = "\n".join(f"See [[Missing {index}]] here." for index in range(20))
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Noisy.md"), "content": GOOD + noise},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    _code, stderr = assert_blocked(result, "KN004")
    assert "and 8 more" in stderr


def test_allows_a_command_with_unbalanced_quotes(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use("Bash", {"command": "rm 'unterminated"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_blocks_malformed_stdin():
    # Arrange
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json at all",
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={
            **os.environ,
            "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            "CLAUDE_BYPASS_STATE": os.devnull,
        },
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr


def test_blocks_on_undecodable_stdin(monkeypatch, vault):
    # Arrange
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
    spec = importlib.util.spec_from_file_location("knowledge_note_guard", hook)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault))
    monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        module.main()

    # Assert
    assert exit_info.value.code == 2

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "gh-token-guard"


def test_blocks_gh_pr_without_token(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh pr list"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_allows_gh_version(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh --version"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_gh_help(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh --help"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_gh_config_get(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh config get editor"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_no_api_call_chained_with_api_call(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh --version && gh pr list"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_blocks_gh_auth_switch(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh auth switch --user alice"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_allows_gh_with_inline_token(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "GH_TOKEN=$(gh auth token --user gufranco) gh pr list"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_gh_with_exported_token(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "export GH_TOKEN=abc && gh pr list"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_gh_auth_status(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh auth status"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_gh_auth_token(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gh auth token --user me"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_unrelated_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "ls -la"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_empty_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "gh-token-guard.py"
    env = {**os.environ, "CLAUDE_HOOK_AUDIT_DISABLE": "1"}

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 0


def test_allows_gh_text_inside_a_single_quoted_pattern(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "rg -n -e 'token --user\\|gh pr create' skills/"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_gh_text_inside_a_quoted_heredoc_body(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "cat <<'EOF' > notes.md\ngh pr create --fill\nEOF"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_real_gh_call_after_a_quoted_string(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "echo 'gh is quoted' && gh pr list"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "GH_TOKEN")


def test_blocks_gh_call_after_a_quoted_heredoc(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "cat <<'EOF'\nnotes\nEOF\ngh pr list"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "GH_TOKEN")


def test_a_quoted_token_assignment_does_not_count(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "echo 'GH_TOKEN=x' && gh pr list"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "GH_TOKEN")

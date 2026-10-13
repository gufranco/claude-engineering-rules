from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "gcloud-config-guard"


def test_blocks_gcloud_config_set(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gcloud config set project foo"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: `gcloud config set ...` without `--configuration=<name>` writes to the active",
    )


def test_blocks_gcloud_config_activate(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gcloud config configurations activate dev"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: `gcloud config configurations activate <name>` switches the active gcloud",
    )


def test_allows_gcloud_config_set_with_configuration_flag(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gcloud config set --configuration=dev project foo"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_gcloud_config_activate_help(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "gcloud config configurations activate --help"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_gcloud_config_list(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "gcloud config list"})

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


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "gcloud-config-guard.py"
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
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr

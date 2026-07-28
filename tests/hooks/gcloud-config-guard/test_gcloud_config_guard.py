"""Coverage for gcloud-config-guard hook.

Source rule: standards/multi-account-cli.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "gcloud-config-guard"


def test_blocks_gcloud_config_set(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "gcloud config set project foo"})

    assert_blocks(HOOK, payload)


def test_blocks_gcloud_config_activate(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "gcloud config configurations activate dev"})

    assert_blocks(HOOK, payload)


def test_allows_gcloud_config_set_with_configuration_flag(tool_use, assert_allows):
    payload = tool_use(
        "Bash",
        {"command": "gcloud config set --configuration=dev project foo"},
    )

    assert_allows(HOOK, payload)


def test_allows_gcloud_config_activate_help(tool_use, assert_allows):
    payload = tool_use(
        "Bash", {"command": "gcloud config configurations activate --help"}
    )

    assert_allows(HOOK, payload)


def test_allows_gcloud_config_list(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "gcloud config list"})

    assert_allows(HOOK, payload)


def test_allows_unrelated_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "ls -la"})

    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": ""})

    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "gcloud-config-guard.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    for k in ("COVERAGE_PROCESS_START", "PYTHONPATH"):
        if k in os.environ:
            env[k] = os.environ[k]

    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    assert proc.returncode == 0

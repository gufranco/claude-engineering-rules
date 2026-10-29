from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from _helpers.cov_env import apply_coverage_env

SCRIPT = (
    Path(__file__).resolve().parents[2] / ".github" / "scripts" / "mcp-server-probe.py"
)


@pytest.fixture
def probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mcp_server_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _home(tmp_path: Path, servers: dict[str, object] | None) -> Path:
    claude = tmp_path / ".claude"
    claude.mkdir()
    if servers is not None:
        (claude / "settings.json").write_text(
            json.dumps({"mcpServers": servers}), encoding="utf-8"
        )
    return tmp_path


def test_every_outcome_is_reported_and_a_failure_fails_the_run(
    probe_module, tmp_path, capsys
):
    # Arrange
    home = _home(
        tmp_path,
        {
            "ok": {"command": "true"},
            "slow": {"command": "sleep", "args": ["10"]},
            "bad": {"command": "false"},
            "remote": {"type": "http", "url": "https://example.invalid/mcp"},
            "spaced": {"command": "test", "args": ["a b", "=", "a b"]},
        },
    )

    # Act
    code = probe_module.main(["--verbose"], home)

    # Assert
    assert code == 1
    assert capsys.readouterr().out == (
        "=== MCP Health Check ===\n\n"
        "PASS (ok): exited cleanly\n"
        "PASS (slow): started successfully (timed out as expected)\n"
        "FAIL (bad): exited with code 1\n"
        "  Command: false\n"
        "SKIP (remote): command not found: \n"
        "PASS (spaced): exited cleanly\n"
        "\nResults: 3 passed, 1 failed, 1 skipped\n"
    )


def test_a_failure_without_verbose_omits_the_command(probe_module, tmp_path, capsys):
    # Arrange
    home = _home(tmp_path, {"bad": {"command": "false"}})

    # Act
    code = probe_module.main([], home)

    # Assert
    assert code == 1
    assert "Command:" not in capsys.readouterr().out


def test_no_configured_servers_exits_zero_with_a_notice(probe_module, tmp_path, capsys):
    # Arrange
    home = _home(tmp_path, {})

    # Act
    code = probe_module.main([], home)

    # Assert
    assert (code, capsys.readouterr().out) == (
        0,
        "No MCP servers configured in settings.json.\n",
    )


def test_a_missing_settings_file_is_an_error(probe_module, tmp_path, capsys):
    # Arrange
    home = _home(tmp_path, None)

    # Act
    code = probe_module.main([], home)

    # Assert
    assert (code, capsys.readouterr().out) == (
        1,
        f"ERROR: settings.json not found at {home}/.claude/settings.json\n",
    )


def test_the_script_runs_as_a_program(tmp_path):
    # Arrange
    home = _home(tmp_path, {"ok": {"command": "true"}})
    env = apply_coverage_env({**os.environ, "HOME": str(home)})

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stdout.splitlines()[-1]) == (
        0,
        "Results: 1 passed, 0 failed, 0 skipped",
    )

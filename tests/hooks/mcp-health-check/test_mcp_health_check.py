"""Coverage for mcp-health-check hook."""

from __future__ import annotations

import json
from pathlib import Path

HOOK = "mcp-health-check"


def _isolated_env(tmp_home: Path) -> dict[str, str]:
    return {"HOME": str(tmp_home)}


def test_allows_non_mcp_tool(tool_use, assert_allows, tmp_path):
    # Arrange
    payload = tool_use("Bash", {"command": "echo hi"})

    # Act / Assert
    assert_allows(HOOK, payload, env=_isolated_env(tmp_path))


def test_allows_mcp_pretool_with_no_state(tool_use, assert_allows, tmp_path):
    # Arrange
    payload = tool_use("mcp__github__create_issue", {"title": "x"})

    # Act / Assert
    assert_allows(HOOK, payload, env=_isolated_env(tmp_path))


def test_allows_mcp_posttool_success(tool_use, assert_allows, tmp_path):
    # Arrange
    payload = tool_use(
        "mcp__github__create_issue",
        {"title": "x"},
        hook_event_name="PostToolUse",
        tool_response={"ok": True},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env=_isolated_env(tmp_path))


def test_allows_mcp_posttool_failure(tool_use, assert_allows, tmp_path):
    # Arrange
    payload = tool_use(
        "mcp__github__create_issue",
        {"title": "x"},
        hook_event_name="PostToolUse",
        tool_response={"error": "rate limited"},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env=_isolated_env(tmp_path))


def test_blocks_after_three_failures(tool_use, run_hook, tmp_path):
    # Arrange
    cache_dir = tmp_path / ".claude" / "cache"
    cache_dir.mkdir(parents=True)
    import time

    (cache_dir / "mcp-health.json").write_text(
        json.dumps({"github": {"failures": 3, "last_failure": time.time()}})
    )
    payload = tool_use("mcp__github__create_issue", {"title": "x"})

    # Act
    code, _out, err = run_hook(HOOK, payload, env=_isolated_env(tmp_path))

    # Assert
    assert code == 2
    assert "unhealthy" in err


def test_allows_with_disable_env(tool_use, run_hook, tmp_path):
    # Arrange
    cache_dir = tmp_path / ".claude" / "cache"
    cache_dir.mkdir(parents=True)
    import time

    (cache_dir / "mcp-health.json").write_text(
        json.dumps({"github": {"failures": 99, "last_failure": time.time()}})
    )
    payload = tool_use("mcp__github__create_issue", {"title": "x"})
    env = _isolated_env(tmp_path)
    env["MCP_HEALTH_DISABLE"] = "1"

    # Act
    code, _out, _err = run_hook(HOOK, payload, env=env)

    # Assert
    assert code == 0


def test_allows_stale_failures(tool_use, run_hook, tmp_path):
    # Arrange
    cache_dir = tmp_path / ".claude" / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "mcp-health.json").write_text(
        json.dumps({"github": {"failures": 99, "last_failure": 0}})
    )
    payload = tool_use("mcp__github__create_issue", {"title": "x"})

    # Act
    code, _out, _err = run_hook(HOOK, payload, env=_isolated_env(tmp_path))

    # Assert
    assert code == 0


def test_allows_invalid_payload_no_mcp_prefix(tool_use, assert_allows, tmp_path):
    # Arrange
    payload = tool_use("github__call", {})

    # Act / Assert
    assert_allows(HOOK, payload, env=_isolated_env(tmp_path))


def test_allows_unknown_event(tool_use, assert_allows, tmp_path):
    # Arrange
    payload = tool_use("mcp__github__call", {}, hook_event_name="SessionStart")

    # Act / Assert
    assert_allows(HOOK, payload, env=_isolated_env(tmp_path))

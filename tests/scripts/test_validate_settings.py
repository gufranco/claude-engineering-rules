from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-settings.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_settings", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_settings = _load()


def _hooks(matcher: str) -> dict[str, object]:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": matcher,
                    "hooks": [{"type": "command", "command": "echo ok"}],
                }
            ]
        }
    }


@pytest.mark.parametrize(
    "matcher",
    [
        "Bash",
        "mcp__.*",
        "mcp__linear-acme__save_issue|mcp__linear-acme__save_comment",
    ],
)
def test_known_tools_and_exact_mcp_tool_names_are_valid_matchers(matcher):
    # Arrange
    data = _hooks(matcher)

    # Act
    result = validate_settings.validate_hooks(data)

    # Assert
    assert result == []


@pytest.mark.parametrize(
    ("matcher", "token"),
    [
        ("Bsh", "Bsh"),
        ("mcp__linear[^_]*__save_issue", "mcp__linear[^_]*__save_issue"),
        ("mcp__server", "mcp__server"),
    ],
)
def test_unknown_matchers_are_reported(matcher, token):
    # Arrange
    data = _hooks(matcher)

    # Act
    result = validate_settings.validate_hooks(data)

    # Assert
    assert result == [f"  Unknown hook matcher '{token}' in PreToolUse"]


def _settings(root, data):
    import json

    (root / "settings.json").write_text(json.dumps(data), encoding="utf-8")


def test_deny_rules_flag_bad_patterns_and_duplicates():
    # Arrange
    data = {"permissions": {"deny": ["Read(./.env)", "Bash", "Read(./.env)", "Agent"]}}

    # Act
    result = validate_settings.validate_deny_rules(data)

    # Assert
    assert result == [
        "  Invalid deny pattern: Bash",
        "  Duplicate deny entry: Read(./.env)",
    ]


def test_mcp_servers_need_a_command_or_url_and_list_args():
    # Arrange
    data = {
        "mcpServers": {
            "a": "not an object",
            "b": {},
            "c": {"command": "x", "args": "y"},
            "d": {"url": "https://x.test"},
        }
    }

    # Act
    result = validate_settings.validate_mcpservers(data)

    # Assert
    assert result == [
        "  mcpServers.a: must be an object",
        "  mcpServers.b: must have either 'command' or 'url'",
        "  mcpServers.c: 'args' must be a list when 'command' is set",
    ]


def test_hook_commands_must_point_at_existing_scripts(tmp_path):
    # Arrange
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "real.py").write_text("", encoding="utf-8")
    data = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {"type": "command"},
                        {"command": "echo plain"},
                        {"command": "python3 ~/.claude/hooks/real.py"},
                        {"command": "python3 ~/.claude/hooks/gone.py"},
                    ]
                }
            ]
        }
    }

    # Act
    result = validate_settings.validate_hooks(data, str(tmp_path))

    # Assert
    assert result == [
        "  Hook script not found: ~/.claude/hooks/gone.py "
        "(resolved to hooks/gone.py) in Stop"
    ]


def test_main_fails_without_a_settings_file(tmp_path, capsys):
    # Arrange
    root = tmp_path

    # Act
    code = validate_settings.main(str(root))

    # Assert
    assert (code, capsys.readouterr().out) == (1, "settings.json not found\n")


def test_main_lists_errors_and_fails(tmp_path, capsys):
    # Arrange
    _settings(tmp_path, {"permissions": {"deny": ["Bash"]}})

    # Act
    code = validate_settings.main(str(tmp_path))

    # Assert
    assert code == 1
    assert "FAILED: 1 error(s) found:\n\n  Invalid deny pattern: Bash\n" in (
        capsys.readouterr().out
    )


def test_main_passes_a_valid_file(tmp_path, capsys):
    # Arrange
    _settings(tmp_path, {})

    # Act
    code = validate_settings.main(str(tmp_path))

    # Assert
    assert (code, capsys.readouterr().out) == (
        0,
        "Validated settings.json: 0 deny rules, 0 hook commands, 0 MCP servers\n"
        "PASSED: settings.json valid\n",
    )


def test_the_script_validates_this_repository():
    # Arrange
    import os
    import subprocess
    import sys

    from _helpers.cov_env import apply_coverage_env

    env = apply_coverage_env(dict(os.environ))

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
        "PASSED: settings.json valid",
    )

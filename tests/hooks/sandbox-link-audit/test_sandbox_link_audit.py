from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed

HOOK = "sandbox-link-audit"


@dataclass(frozen=True, slots=True)
class Layout:
    home: Path
    repo: Path
    scratch: Path
    env: dict[str, str]


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    home = tmp_path / "home"
    repo = home / "dots"
    (repo / "gnupg").mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, timeout=30)
    (repo / ".gitignore").write_text("gnupg/\n", encoding="utf-8")
    temp_root = tmp_path / "tmpdir"
    scratch = temp_root / "claude-1000" / "session" / "scratchpad"
    scratch.mkdir(parents=True)
    env = {"HOME": str(home), "TMPDIR": f"{temp_root}/"}
    return Layout(home, repo, scratch, env)


def _stop(tool_use, run_hook, layout: Layout, cwd: Path, active: bool = False):
    payload = tool_use(
        "", hook_event_name="Stop", cwd=str(cwd), stop_hook_active=active
    )
    return run_hook(HOOK, payload, env=layout.env)


def test_an_ignored_link_into_the_scratchpad_blocks_the_stop(
    tool_use, run_hook, layout
):
    # Arrange
    target = layout.scratch / "agent.conf"
    target.write_text("x\n", encoding="utf-8")
    (layout.repo / "gnupg" / "agent.conf").symlink_to(target)

    # Act
    result = _stop(tool_use, run_hook, layout, layout.repo / "gnupg")

    # Assert
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "gnupg/agent.conf" in decision["reason"]


def test_a_home_dotfile_pointing_into_a_temp_dir_is_reported(
    tool_use, run_hook, layout
):
    # Arrange
    (layout.home / ".gnupg").symlink_to(layout.scratch)

    # Act
    result = _stop(tool_use, run_hook, layout, layout.repo)

    # Assert
    assert ".gnupg" in json.loads(result.stdout)["reason"]


def test_a_config_entry_pointing_into_a_temp_dir_is_reported(
    tool_use, run_hook, layout
):
    # Arrange
    folder = layout.home / ".config" / "tool"
    folder.mkdir(parents=True)
    (folder / "config.toml").symlink_to(layout.scratch / "gone.toml")

    # Act
    result = _stop(tool_use, run_hook, layout, layout.repo)

    # Assert
    assert "config.toml" in json.loads(result.stdout)["reason"]


def test_a_clean_tree_passes_silently(tool_use, run_hook, layout):
    # Arrange
    (layout.repo / "inner").symlink_to(layout.repo / "gnupg")

    # Act
    result = _stop(tool_use, run_hook, layout, layout.repo)

    # Assert
    assert_allowed(result)
    assert result.stdout == ""


def test_dependency_folders_are_not_walked(tool_use, run_hook, layout):
    # Arrange
    modules = layout.repo / "node_modules"
    modules.mkdir()
    (modules / "pkg").symlink_to(layout.scratch)

    # Act
    result = _stop(tool_use, run_hook, layout, layout.repo)

    # Assert
    assert result.stdout == ""


def test_a_second_stop_only_warns(tool_use, run_hook, layout):
    # Arrange
    (layout.repo / "gnupg" / "agent.conf").symlink_to(layout.scratch / "a")

    # Act
    result = _stop(tool_use, run_hook, layout, layout.repo, active=True)

    # Assert
    assert "agent.conf" in json.loads(result.stdout)["systemMessage"]


def test_a_session_working_inside_a_temp_dir_is_not_scanned(tool_use, run_hook, layout):
    # Arrange
    (layout.scratch / "link").symlink_to(layout.scratch / "a")

    # Act
    result = _stop(tool_use, run_hook, layout, layout.scratch)

    # Assert
    assert result.stdout == ""


def test_the_disable_variable_skips_the_audit(tool_use, run_hook, layout):
    # Arrange
    (layout.repo / "gnupg" / "agent.conf").symlink_to(layout.scratch / "a")
    payload = tool_use("", hook_event_name="Stop", cwd=str(layout.repo))
    env = {**layout.env, "SANDBOX_LINK_DISABLE": "1"}

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert result.stdout == ""


def test_a_missing_home_config_folder_is_fine(tool_use, run_hook, layout):
    # Arrange
    cwd = layout.repo

    # Act
    result = _stop(tool_use, run_hook, layout, cwd)

    # Assert
    assert_allowed(result)

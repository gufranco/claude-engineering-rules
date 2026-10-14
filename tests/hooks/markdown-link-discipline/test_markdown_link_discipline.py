from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from _helpers.cov_env import apply_coverage_env
from _helpers.hook_assertions import assert_allowed

HOOK = "markdown-link-discipline"
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_ROOT / "hooks" / "markdown-link-discipline.py"
TRACKED_TARGET = "rules/security.md"
BARE_MENTION = f"Read `{TRACKED_TARGET}` first.\n"
LINKED_MENTION = f"Read [`{TRACKED_TARGET}`](../{TRACKED_TARGET}) first.\n"
BLOCK_MSG = "BLOCKED: markdown link discipline."
TIMEOUT_S = 30
Runner = Callable[[dict], tuple[int, str]]


@pytest.fixture()
def hook(
    scratch_repo_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> ModuleType:
    target = scratch_repo_root / TRACKED_TARGET
    target.parent.mkdir(parents=True)
    target.write_text("# Security\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(scratch_repo_root), "add", TRACKED_TARGET],
        check=True,
        timeout=TIMEOUT_S,
    )
    monkeypatch.setenv("CLAUDE_HOOK_AUDIT_DISABLE", "1")
    monkeypatch.delenv("MARKDOWN_LINKS_DISABLE", raising=False)
    spec = importlib.util.spec_from_file_location("_mld_mod", str(HOOK_PATH))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr("_lib.bypass.STATE_PATH", tmp_path / "bypass-state.json")
    return module


@pytest.fixture()
def run_in_repo(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> Runner:
    def _run(payload: dict) -> tuple[int, str]:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        with pytest.raises(SystemExit) as exit_info:
            hook.main()
        return int(exit_info.value.code or 0), capsys.readouterr().err

    return _run


def _doc(root: Path, name: str, text: str) -> Path:
    path = root / "docs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_allows_non_markdown_file(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "foo.py"), "content": "print('hi')"},
    )

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


def test_blocks_a_new_bare_reference_to_a_tracked_file(
    tool_use, run_in_repo: Runner, scratch_repo_root: Path
):
    # Arrange
    target = _doc(scratch_repo_root, "blocked.md", "")
    payload = tool_use("Write", {"file_path": str(target), "content": BARE_MENTION})

    # Act
    code, stderr = run_in_repo(payload)

    # Assert
    assert code == 2
    assert BLOCK_MSG in stderr
    assert "The change to docs/blocked.md introduces 1 new bare" in stderr


def test_allows_markdown_with_linked_references(
    tool_use, run_in_repo: Runner, scratch_repo_root: Path
):
    # Arrange
    target = _doc(scratch_repo_root, "linked.md", "# Doc\n")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "# Doc\n",
            "new_string": "# Doc\n\n" + LINKED_MENTION,
        },
    )

    # Act
    code, stderr = run_in_repo(payload)

    # Assert
    assert (code, stderr) == (0, "")


def test_allows_advisory_specs_directory(
    tool_use, run_in_repo: Runner, scratch_repo_root: Path
):
    # Arrange
    target = scratch_repo_root / "specs" / "advisory.md"
    target.parent.mkdir()
    target.write_text("", encoding="utf-8")
    payload = tool_use("Write", {"file_path": str(target), "content": BARE_MENTION})

    # Act
    code, stderr = run_in_repo(payload)

    # Assert
    assert (code, stderr) == (0, "")


def test_allows_a_bare_reference_when_the_bypass_env_is_set(
    tool_use, run_in_repo: Runner, scratch_repo_root: Path, monkeypatch
):
    # Arrange
    target = _doc(scratch_repo_root, "bypassed.md", "")
    payload = tool_use("Write", {"file_path": str(target), "content": BARE_MENTION})
    monkeypatch.setenv("MARKDOWN_LINKS_DISABLE", "1")

    # Act
    code, stderr = run_in_repo(payload)

    # Assert
    assert (code, stderr) == (0, "")


def test_allows_a_mention_of_a_path_that_does_not_exist(
    tool_use, run_in_repo: Runner, scratch_repo_root: Path
):
    # Arrange
    target = _doc(scratch_repo_root, "hypothetical.md", "")
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "Hypothetical `foo/bar/baz.md` example.\n",
        },
    )

    # Act
    code, stderr = run_in_repo(payload)

    # Assert
    assert (code, stderr) == (0, "")


def test_allows_an_edit_that_keeps_a_pre_existing_bare_reference(
    tool_use, run_in_repo: Runner, scratch_repo_root: Path
):
    # Arrange
    target = _doc(scratch_repo_root, "legacy.md", "Existing. " + BARE_MENTION)
    payload = tool_use(
        "Edit",
        {"file_path": str(target), "old_string": "Existing", "new_string": "Updated"},
    )

    # Act
    code, stderr = run_in_repo(payload)

    # Assert
    assert (code, stderr) == (0, "")


def test_allows_a_bare_reference_in_a_file_outside_any_repository(
    tool_use, run_in_repo: Runner, tmp_path: Path
):
    # Arrange
    target = tmp_path / "loose" / "notes.md"
    payload = tool_use("Write", {"file_path": str(target), "content": BARE_MENTION})

    # Act
    code, stderr = run_in_repo(payload)

    # Assert
    assert (code, stderr) == (0, "")


def test_invalid_json_stdin_blocks():
    # Arrange
    stdin = "not valid json"

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=TIMEOUT_S,
        check=False,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr


def test_blocks_a_bare_reference_in_a_repository_outside_the_config_repo(
    tool_use, scratch_repo_root: Path
):
    # Arrange
    tracked = scratch_repo_root / TRACKED_TARGET
    tracked.parent.mkdir(parents=True)
    tracked.write_text("# Security\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(scratch_repo_root), "add", TRACKED_TARGET],
        check=True,
        timeout=TIMEOUT_S,
    )
    target = _doc(scratch_repo_root, "outside.md", "")
    payload = tool_use("Write", {"file_path": str(target), "content": BARE_MENTION})
    env = {
        key: value
        for key, value in os.environ.items()
        if key != "MARKDOWN_LINKS_DISABLE"
    }
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=apply_coverage_env(env),
        timeout=TIMEOUT_S,
        check=False,
    )

    # Assert
    assert proc.returncode == 2
    assert "The change to docs/outside.md introduces 1 new bare" in proc.stderr

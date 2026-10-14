from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "immutability-analyzers"
CLEAN_PY = "def f(items=None):\n    return list(items or [])\n"
DIRTY_PY = "def f(items=[]):\n    return items\n"
FULL_BATCH_STOP_TIMEOUT_S = 30.0


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@test.local",
            *args,
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, object]:
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    pyright = stubs / "pyright"
    pyright.write_text(
        "#!/bin/sh\necho '{\"generalDiagnostics\": []}'\n", encoding="utf-8"
    )
    pyright.chmod(0o755)
    ruff_dir = str(Path(sys.executable).parent)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    env = {
        "PATH": os.pathsep.join([str(stubs), ruff_dir, "/usr/bin", "/bin"]),
        "CLAUDE_ANALYZER_CACHE": str(tmp_path / "cache"),
    }
    return {"repo": repo, "env": env}


def _record(run_hook, env: dict[str, str], path: Path) -> None:
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "tool_name": "Write",
        "tool_input": {"file_path": str(path), "content": ""},
    }
    assert_allowed(run_hook(HOOK, payload, env=env))


def _stop(
    run_hook,
    env: dict[str, str],
    *,
    active: bool = False,
    **run_options: float,
):
    payload = {
        "hook_event_name": "Stop",
        "session_id": "s1",
        "stop_hook_active": active,
    }
    return run_hook(HOOK, payload, env=env, **run_options)


def test_stop_blocks_a_new_file_with_a_finding(run_hook, workspace):
    # Arrange
    source = workspace["repo"] / "core.py"
    source.write_text(DIRTY_PY, encoding="utf-8")
    _record(run_hook, workspace["env"], source)

    # Act
    result = _stop(run_hook, workspace["env"])

    # Assert
    decision = json.loads(result.stdout)
    assert (decision["decision"], "B006" in decision["reason"]) == ("block", True)


def test_stop_passes_a_clean_file_and_clears_the_batch(run_hook, workspace):
    # Arrange
    source = workspace["repo"] / "core.py"
    source.write_text(CLEAN_PY, encoding="utf-8")
    _record(run_hook, workspace["env"], source)

    # Act
    result = _stop(run_hook, workspace["env"])

    # Assert
    assert (result.code, result.stdout.strip()) == (0, "")
    assert list((Path(workspace["env"]["CLAUDE_ANALYZER_CACHE"])).glob("*.txt")) == []


def test_preexisting_finding_on_an_untouched_line_is_advisory(run_hook, workspace):
    # Arrange
    repo = workspace["repo"]
    source = repo / "core.py"
    source.write_text(DIRTY_PY + "\n\nVALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "core.py")
    _git(repo, "commit", "-q", "--no-gpg-sign", "-m", "base")
    source.write_text(DIRTY_PY + "\n\nVALUE = 2\n", encoding="utf-8")
    _record(run_hook, workspace["env"], source)

    # Act
    result = _stop(run_hook, workspace["env"])

    # Assert
    message = json.loads(result.stdout)
    assert ("decision" in message, "pre-existing" in message["systemMessage"]) == (
        False,
        True,
    )


def test_missing_analyzer_blocks(run_hook, workspace):
    # Arrange
    source = workspace["repo"] / "a.lua"
    source.write_text("local x = 1\nreturn x\n", encoding="utf-8")
    _record(run_hook, workspace["env"], source)

    # Act
    result = _stop(run_hook, workspace["env"])

    # Assert
    decision = json.loads(result.stdout)
    assert (
        decision["decision"],
        "luacheck is not installed" in decision["reason"],
    ) == ("block", True)


def test_identical_findings_after_a_block_reach_the_user_instead(run_hook, workspace):
    # Arrange
    source = workspace["repo"] / "core.py"
    source.write_text(DIRTY_PY, encoding="utf-8")
    _record(run_hook, workspace["env"], source)
    _stop(run_hook, workspace["env"])

    # Act
    result = _stop(run_hook, workspace["env"], active=True)

    # Assert
    message = json.loads(result.stdout)
    assert ("decision" in message, "B006" in message["systemMessage"]) == (False, True)


def test_out_of_scope_files_are_not_recorded(run_hook, workspace):
    # Arrange
    tests_dir = workspace["repo"] / "tests"
    tests_dir.mkdir()
    source = tests_dir / "test_core.py"
    source.write_text(DIRTY_PY, encoding="utf-8")
    _record(run_hook, workspace["env"], source)

    # Act
    result = _stop(run_hook, workspace["env"])

    # Assert
    assert (result.code, result.stdout.strip()) == (0, "")


def test_disable_env_short_circuits(run_hook, workspace):
    # Arrange
    source = workspace["repo"] / "core.py"
    source.write_text(DIRTY_PY, encoding="utf-8")
    _record(run_hook, workspace["env"], source)
    env = {**workspace["env"], "IMMUTABILITY_ANALYZERS_DISABLE": "1"}

    # Act
    result = _stop(run_hook, env)

    # Assert
    assert (result.code, result.stdout.strip()) == (0, "")


def test_blocks_a_payload_that_is_not_an_object(run_hook):
    # Arrange
    command = "not-json"

    # Act
    result = run_hook(HOOK, command)

    # Assert
    assert_blocked(result, "could not read its input")


def test_profile_disable_short_circuits(run_hook, workspace):
    # Arrange
    env = {**workspace["env"], "CLAUDE_DISABLED_HOOKS": HOOK}

    # Act
    result = _stop(run_hook, env)

    # Assert
    assert (result.code, result.stdout.strip()) == (0, "")


def test_other_events_do_nothing(run_hook, workspace):
    # Arrange
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
    }

    # Act
    result = run_hook(HOOK, payload, env=workspace["env"])

    # Assert
    assert (result.code, result.stdout.strip()) == (0, "")


def test_rules_outside_the_catalog_are_ignored(run_hook, workspace, tmp_path):
    # Arrange
    pyright = Path(workspace["env"]["PATH"].split(os.pathsep)[0]) / "pyright"
    report = {
        "generalDiagnostics": [
            {
                "file": "X",
                "rule": "reportMissingImports",
                "range": {"start": {"line": 0}},
                "message": "m",
            }
        ]
    }
    pyright.write_text(f"#!/bin/sh\necho '{json.dumps(report)}'\n", encoding="utf-8")
    source = workspace["repo"] / "core.py"
    source.write_text(CLEAN_PY, encoding="utf-8")
    report["generalDiagnostics"][0]["file"] = str(source.resolve())
    pyright.write_text(f"#!/bin/sh\necho '{json.dumps(report)}'\n", encoding="utf-8")
    _record(run_hook, workspace["env"], source)

    # Act
    result = _stop(run_hook, workspace["env"])

    # Assert
    assert (result.code, result.stdout.strip()) == (0, "")


def test_files_past_the_per_turn_cap_stay_queued(run_hook, workspace):
    # Arrange
    ruff = Path(workspace["env"]["PATH"].split(os.pathsep)[0]) / "ruff"
    ruff.write_text("#!/bin/sh\necho '[]'\n", encoding="utf-8")
    ruff.chmod(0o755)
    sources = [workspace["repo"] / f"m{index}.py" for index in range(41)]
    for source in sources:
        source.write_text(CLEAN_PY, encoding="utf-8")
        _record(run_hook, workspace["env"], source)

    # Act
    result = _stop(run_hook, workspace["env"], timeout=FULL_BATCH_STOP_TIMEOUT_S)

    # Assert
    message = json.loads(result.stdout)
    queue = Path(workspace["env"]["CLAUDE_ANALYZER_CACHE"]) / "analyzer-batch-s1.txt"
    assert (
        "1 more edited files were not analyzed" in message["systemMessage"],
        queue.read_text(encoding="utf-8").splitlines(),
    ) == (True, [str(sources[-1].resolve())])

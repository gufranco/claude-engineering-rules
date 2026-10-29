from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

ROOT = Path(__file__).resolve().parents[3]
HOOK = "force-push-during-review"
HOOK_PATH = ROOT / "hooks" / f"{HOOK}.py"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tests"))

from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _lib.bypass_writer import set_bypass  # noqa: E402

FORCE_PUSH = "git push " + "--" + "force origin feat"
SYSTEM_PATH = "/usr/bin:/bin"
BRANCH_OK = (
    'case "$*" in *remote*) echo git@github.com:o/r.git ;; *) echo feat ;; esac\n'
)
GITLAB_BRANCH = (
    'case "$*" in *remote*) echo git@gitlab.com:o/r.git ;; *) echo feat ;; esac\n'
)
NO_PR = 'echo "no pull requests found for branch feat" >&2\nexit 1\n'
REVIEWER = "rev-" + "alpha"


def _bin(
    directory: Path, scripts: dict[str, str], system_path: str = SYSTEM_PATH
) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in scripts.items():
        stub = directory / name
        stub.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        stub.chmod(0o755)
    return ":".join(part for part in (str(directory), system_path) if part)


def test_an_open_changes_requested_review_blocks(tmp_path, tool_use, run_hook):
    # Arrange
    path = _bin(tmp_path / "bin", {"git": BRANCH_OK, "gh": f"echo {REVIEWER}\n"})
    payload = tool_use("Bash", {"command": FORCE_PUSH})

    # Act
    result = run_hook(HOOK, payload, env={"PATH": path})

    # Assert
    _code, stderr = assert_blocked(result, "force-push during open")
    assert f"Reviewer `{REVIEWER}`" in stderr


@pytest.mark.parametrize(
    "scripts",
    [
        {"git": "exit 1\n", "gh": f"echo {REVIEWER}\n"},
        {"git": "echo\n", "gh": f"echo {REVIEWER}\n"},
        {"git": BRANCH_OK, "gh": NO_PR},
        {"git": BRANCH_OK, "gh": "echo\n"},
        {"git": GITLAB_BRANCH, "gh": f"echo {REVIEWER}\n"},
    ],
    ids=["no-repo", "no-branch", "no-pull-request", "no-blocking-review", "not-github"],
)
def test_a_branch_with_nothing_to_protect_allows(scripts, tmp_path, tool_use, run_hook):
    # Arrange
    path = _bin(tmp_path / "bin", scripts)
    payload = tool_use("Bash", {"command": FORCE_PUSH})

    # Act
    result = run_hook(HOOK, payload, env={"PATH": path})

    # Assert
    assert_allowed(result)


def test_a_missing_git_allows(tmp_path, tool_use, run_hook):
    # Arrange
    empty = tmp_path / "empty"
    empty.mkdir()
    payload = tool_use("Bash", {"command": FORCE_PUSH})

    # Act
    result = run_hook(HOOK, payload, env={"PATH": str(empty)})

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "env",
    [{"FORCE_PUSH_DURING_REVIEW_DISABLE": "1"}, {"CLAUDE_DISABLED_HOOKS": HOOK}],
)
def test_an_explicit_switch_allows(env, tmp_path, tool_use, run_hook):
    # Arrange
    path = _bin(tmp_path / "bin", {"git": BRANCH_OK, "gh": f"echo {REVIEWER}\n"})
    payload = tool_use("Bash", {"command": FORCE_PUSH})

    # Act
    result = run_hook(HOOK, payload, env={"PATH": path, **env})

    # Assert
    assert_allowed(result)


def test_a_live_bypass_entry_allows(tmp_path, tool_use, run_hook):
    # Arrange
    path = _bin(tmp_path / "bin", {"git": BRANCH_OK, "gh": f"echo {REVIEWER}\n"})
    state = tmp_path / "bypass.json"
    set_bypass(HOOK, ttl_seconds=120, state_path=state)
    payload = tool_use("Bash", {"command": FORCE_PUSH})

    # Act
    result = run_hook(
        HOOK, payload, env={"PATH": path, "CLAUDE_BYPASS_STATE": str(state)}
    )

    # Assert
    assert_allowed(result)


def test_a_payload_that_is_not_json_blocks():
    # Arrange
    env = apply_coverage_env(dict(os.environ))

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert (proc.returncode, "could not read its input" in proc.stderr) == (2, True)


def test_a_push_spelled_with_extra_spacing_and_no_force_is_not_forced():
    # Arrange
    spec = importlib.util.spec_from_file_location("_fpdr_lookup", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Act
    detected = module.is_force_push("git  push origin feat")

    # Assert
    assert detected is False


@pytest.mark.parametrize(
    ("scripts", "system_path"),
    [
        ({"git": BRANCH_OK, "gh": "echo boom >&2\nexit 1\n"}, SYSTEM_PATH),
        ({"git": BRANCH_OK}, ""),
    ],
    ids=["gh-error", "gh-missing"],
)
def test_a_lookup_that_cannot_answer_blocks(
    scripts, system_path, tmp_path, tool_use, run_hook
):
    # Arrange
    path = _bin(tmp_path / "bin", scripts, system_path)
    payload = tool_use("Bash", {"command": FORCE_PUSH})

    # Act
    result = run_hook(HOOK, payload, env={"PATH": path})

    # Assert
    assert_blocked(result, "could not be read")


def test_only_each_reviewers_latest_review_counts(tmp_path, tool_use, run_hook):
    # Arrange
    gh = f'case "$*" in *latestReviews*) echo ;; *) echo {REVIEWER} ;; esac\n'
    path = _bin(tmp_path / "bin", {"git": BRANCH_OK, "gh": gh})
    payload = tool_use("Bash", {"command": FORCE_PUSH})

    # Act
    result = run_hook(HOOK, payload, env={"PATH": path})

    # Assert
    assert_allowed(result)

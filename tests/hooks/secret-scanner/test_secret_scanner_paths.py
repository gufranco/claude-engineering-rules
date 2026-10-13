from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

ROOT = Path(__file__).resolve().parents[3]
HOOK = "secret-scanner"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tests"))

from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _lib.bypass_writer import set_bypass  # noqa: E402

FAKE_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
COMMIT = "git commit -m 'fix: y'"


def _repo_with(tmp_path: Path, files: dict[str, str]) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=30)
    for name, body in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        subprocess.run(
            ["git", "add", "-f", name], check=True, cwd=str(tmp_path), timeout=30
        )
    return tmp_path


def _stub_git(directory: Path, script: str) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    stub = directory / "git"
    stub.write_text("#!/bin/sh\n" + script, encoding="utf-8")
    stub.chmod(0o755)
    return {"PATH": str(directory)}


@pytest.mark.parametrize(
    "name",
    [
        "node_modules/pkg/index.js",
        "src/vendor/lib.js",
        ".env.example",
        "assets/logo.png",
        "poetry.lock",
    ],
)
def test_a_skipped_file_is_not_scanned(name, tmp_path, monkeypatch, tool_use, run_hook):
    # Arrange
    repo = _repo_with(tmp_path, {name: f"KEY = '{FAKE_KEY}'\n"})
    monkeypatch.chdir(repo)
    payload = tool_use("Bash", {"command": COMMIT})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_secret_after_clean_lines_is_found(tmp_path, monkeypatch, tool_use, run_hook):
    # Arrange
    body = "import os\nNAME = 'app'\n" + f"KEY = '{FAKE_KEY}'\n"
    repo = _repo_with(tmp_path, {"settings.py": body, "README.txt": "hello\n"})
    monkeypatch.chdir(repo)
    payload = tool_use("Bash", {"command": COMMIT})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "settings.py:3: AWS Access Key")


def test_clean_staged_files_are_allowed(tmp_path, monkeypatch, tool_use, run_hook):
    # Arrange
    repo = _repo_with(tmp_path, {"app.py": "print('ok')\n", "LICENSE": "MIT\n"})
    monkeypatch.chdir(repo)
    payload = tool_use("Bash", {"command": COMMIT})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "script",
    [
        "exit 1\n",
        'case "$*" in *name-only*) echo app.py; exit 0;; esac\nexit 1\n',
        'case "$*" in *name-only*) /bin/rm -f "$0"; echo app.py; exit 0;; esac\n',
    ],
)
def test_a_directory_git_does_not_recognize_as_a_repository_passes(
    script, tmp_path, tool_use, run_hook
):
    # Arrange
    env = _stub_git(tmp_path / "bin", script)
    payload = tool_use("Bash", {"command": COMMIT})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_diff_that_fails_inside_a_repository_blocks(tmp_path, tool_use, run_hook):
    # Arrange
    script = 'case "$*" in *rev-parse*) echo .git; exit 0;; esac\nexit 1\n'
    env = _stub_git(tmp_path / "bin", script)
    payload = tool_use("Bash", {"command": COMMIT})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "could not read what this commit would record")


def test_a_missing_git_reads_as_nothing_to_scan(tmp_path, tool_use, run_hook):
    # Arrange
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    payload = tool_use("Bash", {"command": COMMIT})

    # Act
    result = run_hook(HOOK, payload, env={"PATH": str(empty)})

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "env",
    [{"SECRET_SCANNER_DISABLE": "1"}, {"CLAUDE_DISABLED_HOOKS": HOOK}],
)
def test_an_explicit_switch_turns_the_scanner_off(
    env, tmp_path, monkeypatch, tool_use, run_hook
):
    # Arrange
    repo = _repo_with(tmp_path, {"config.py": f"KEY = '{FAKE_KEY}'\n"})
    monkeypatch.chdir(repo)
    payload = tool_use("Bash", {"command": COMMIT})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_live_bypass_entry_turns_the_scanner_off(
    tmp_path, monkeypatch, tool_use, run_hook
):
    # Arrange
    repo = _repo_with(tmp_path / "repo", {"config.py": f"KEY = '{FAKE_KEY}'\n"})
    state = tmp_path / "bypass.json"
    set_bypass(HOOK, ttl_seconds=120, state_path=state)
    monkeypatch.chdir(repo)
    payload = tool_use("Bash", {"command": COMMIT})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert_allowed(result)


def test_a_payload_that_is_not_json_blocks():
    # Arrange
    env = apply_coverage_env(dict(os.environ))

    # Act
    proc = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / f"{HOOK}.py")],
        input="not json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert (proc.returncode, "could not read its input" in proc.stderr) == (2, True)

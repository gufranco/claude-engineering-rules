"""Top-level pytest harness for `~/.claude/hooks/*.py` and `~/.claude/scripts/*.py`.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.2.1.

This is the canonical harness. Per-hook conftest files (e.g.,
`tests/hooks/mutation-method-blocker/conftest.py`) layer extra
hook-specific fixtures on top, but every hook can be exercised through
the four primitives exported here:

  - `tool_use(...)`            build a Claude Code v1 payload dict
  - `assert_blocks(...)`       run the hook, assert exit 2 + stderr substring
  - `assert_allows(...)`       run the hook, assert exit 0
  - `assert_modifies_input(...)` run the hook, parse the v2 envelope,
                                 assert `modifiedInput` matches `expected_diff`

The harness invokes the hook as a subprocess to test entry/exit
end-to-end. Coverage of the subprocess is stitched back into the parent
run via `COVERAGE_PROCESS_START` plus `tests/_subprocess_cov`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "hooks"
SUBPROCESS_TIMEOUT_S = 6.0
SUBPROCESS_COV_DIR = REPO_ROOT / "tests" / "_subprocess_cov"
COVERAGERC_PATH = REPO_ROOT / ".coveragerc"


def _hook_path(name: str) -> Path:
    """Resolve a hook by basename. Accepts `mutation-method-blocker` or
    `mutation-method-blocker.py`. Raises FileNotFoundError if absent."""
    candidate = name if name.endswith(".py") else f"{name}.py"
    path = HOOKS_DIR / candidate
    if not path.is_file():
        raise FileNotFoundError(f"hook not found: {path}")
    return path


def _coverage_active() -> bool:
    """True when the parent pytest run is collecting coverage data.

    Detects four independent signals:
      1. `COVERAGE_PROCESS_START` already set (manual coverage run).
      2. `COVERAGE_RUN` set (legacy detection).
      3. `coverage` module loaded with an active controller.
      4. `pytest_cov` plugin loaded (pytest-cov 7.x path).

    Returning True triggers the harness to propagate coverage env vars to
    every subprocess so hook lines run in subprocesses are stitched into
    the parent report.
    """
    if "COVERAGE_PROCESS_START" in os.environ or "COVERAGE_RUN" in os.environ:
        return True
    if "pytest_cov" in sys.modules or "pytest_cov.plugin" in sys.modules:
        return True
    cov_module = sys.modules.get("coverage")
    if cov_module is None:
        return False
    current = getattr(cov_module, "Coverage", None)
    if current is None:
        return False
    return getattr(current, "current", lambda: None)() is not None


def _build_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    if _coverage_active():
        env["COVERAGE_PROCESS_START"] = str(COVERAGERC_PATH)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{SUBPROCESS_COV_DIR}{os.pathsep}{existing_pp}"
            if existing_pp
            else str(SUBPROCESS_COV_DIR)
        )
    if extra:
        env.update(extra)
    return env


def _run_hook(
    hook: str | Path,
    payload: dict[str, Any],
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    path = hook if isinstance(hook, Path) else _hook_path(hook)
    proc = subprocess.run(
        [sys.executable, str(path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_build_env(env),
        timeout=SUBPROCESS_TIMEOUT_S,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


@pytest.fixture
def tool_use() -> Callable[..., dict[str, Any]]:
    """Build a Claude Code PreToolUse / PostToolUse payload.

    Required:
      tool_name          one of Write, Edit, MultiEdit, Bash, Read, ...
      tool_input         dict matching the tool's input schema
    Optional:
      hook_event_name    PreToolUse (default), PostToolUse, ...
      cwd, session_id, transcript_path, permission_mode

    Returns a fresh dict so callers can mutate without cross-test leakage.
    """

    def _build(
        tool_name: str,
        tool_input: dict[str, Any] | None = None,
        *,
        hook_event_name: str = "PreToolUse",
        cwd: str | None = None,
        session_id: str | None = None,
        transcript_path: str | None = None,
        permission_mode: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool_name": tool_name,
            "tool_input": dict(tool_input or {}),
            "hook_event_name": hook_event_name,
        }
        if cwd is not None:
            payload["cwd"] = cwd
        if session_id is not None:
            payload["session_id"] = session_id
        if transcript_path is not None:
            payload["transcript_path"] = transcript_path
        if permission_mode is not None:
            payload["permission_mode"] = permission_mode
        for k, v in extra.items():
            payload[k] = v
        return payload

    return _build


@pytest.fixture
def assert_blocks() -> Callable[..., tuple[int, str]]:
    """Run `hook` against `payload`. Assert exit code 2 and that stderr
    contains `reason_substring`. Returns `(exit_code, stderr)` for further
    inspection."""

    def _check(
        hook: str | Path,
        payload: dict[str, Any],
        reason_substring: str = "",
        *,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        code, _stdout, stderr = _run_hook(hook, payload, env=env)
        assert code == 2, (
            f"expected hook to block (exit 2) but got exit {code}.\nstderr:\n{stderr}"
        )
        if reason_substring:
            assert reason_substring in stderr, (
                f"expected stderr to contain {reason_substring!r}.\nstderr:\n{stderr}"
            )
        return code, stderr

    return _check


@pytest.fixture
def assert_allows() -> Callable[..., tuple[int, str]]:
    """Run `hook` against `payload`. Assert exit code 0. Returns
    `(exit_code, stderr)` for further inspection."""

    def _check(
        hook: str | Path,
        payload: dict[str, Any],
        *,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        code, _stdout, stderr = _run_hook(hook, payload, env=env)
        assert code == 0, (
            f"expected hook to allow (exit 0) but got exit {code}.\nstderr:\n{stderr}"
        )
        return code, stderr

    return _check


@pytest.fixture
def assert_modifies_input() -> Callable[..., dict[str, Any]]:
    """Run `hook` against `payload`. Assert exit 0 and a v2
    `hookSpecificOutput.modifiedInput` envelope matching `expected_diff`.

    `expected_diff` is a partial dict. Every key/value listed must equal
    the corresponding entry in the parsed `modifiedInput`. Extra keys in
    `modifiedInput` are tolerated. Returns the full parsed envelope.
    """

    def _check(
        hook: str | Path,
        payload: dict[str, Any],
        expected_diff: dict[str, Any],
        *,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        code, stdout, stderr = _run_hook(hook, payload, env=env)
        assert code == 0, (
            f"expected hook to allow with modified input (exit 0) "
            f"but got exit {code}.\nstderr:\n{stderr}"
        )
        assert stdout.strip(), (
            "expected hook to print a v2 envelope on stdout but stdout was empty"
        )
        parsed = json.loads(stdout)
        spec = parsed.get("hookSpecificOutput") or {}
        assert spec.get("permissionDecision") == "allow", (
            f"expected permissionDecision=allow, got {spec.get('permissionDecision')!r}"
        )
        modified = spec.get("modifiedInput")
        assert isinstance(modified, dict), (
            f"expected modifiedInput to be a dict, got {type(modified).__name__}"
        )
        for k, v in expected_diff.items():
            assert k in modified, f"expected modifiedInput to include key {k!r}"
            assert modified[k] == v, (
                f"expected modifiedInput[{k!r}] == {v!r}, got {modified[k]!r}"
            )
        return parsed

    return _check


@pytest.fixture
def run_hook() -> Callable[..., tuple[int, str, str]]:
    """Lower-level fixture for tests that need raw stdout. Most tests
    should use `assert_blocks`, `assert_allows`, or `assert_modifies_input`.
    """

    def _runner(
        hook: str | Path,
        payload: dict[str, Any],
        *,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        return _run_hook(hook, payload, env=env)

    return _runner


@pytest.fixture(scope="session")
def hooks_dir() -> Path:
    return HOOKS_DIR


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT

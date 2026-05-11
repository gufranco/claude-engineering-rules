"""Test harness for the mutation-method-blocker hook.

Provides:

  - `run_hook(payload, env=None)`: runs the hook as a subprocess against a
    JSON payload and returns `(exit_code, stderr)`. Audit logging is muted
    via `CLAUDE_HOOK_AUDIT_DISABLE=1` so the suite does not pollute the real
    audit log under `~/.claude/logs/`.
  - `make_payload(tool, file_path, content)`: builds the JSON payload
    dispatched to the hook stdin. Supports Write, Edit, MultiEdit shapes.

The harness deliberately runs the hook as a subprocess (instead of importing
its `main()`) so that:

  - Hook entry/exit code is tested end-to-end.
  - sys.path manipulation inside the hook is exercised.
  - subprocess timeouts catch infinite loops without hanging the suite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
HOOK_PATH = HOOKS_DIR / "mutation-method-blocker.py"
AS_ANY_HOOK = HOOKS_DIR / "as-any-blocker.py"
CONSOLE_LOG_HOOK = HOOKS_DIR / "console-log-blocker.py"
SUBPROCESS_TIMEOUT_S = 6.0
SUBPROCESS_COV_DIR = REPO_ROOT / "tests" / "_subprocess_cov"
COVERAGERC_PATH = REPO_ROOT / ".coveragerc"


@pytest.fixture(scope="session")
def hook_path() -> Path:
    return HOOK_PATH


@pytest.fixture(scope="session")
def as_any_hook_path() -> Path:
    return AS_ANY_HOOK


@pytest.fixture(scope="session")
def console_log_hook_path() -> Path:
    return CONSOLE_LOG_HOOK


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def _coverage_active() -> bool:
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


def run_hook_subprocess(
    hook: Path,
    payload: dict,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run the hook with a JSON payload over stdin.

    Returns (exit_code, stdout, stderr). Tests typically only inspect
    exit_code and stderr (the hook prints human-readable output to stderr
    per the Claude Code hook contract).
    """
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_build_env(env),
        timeout=SUBPROCESS_TIMEOUT_S,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


@pytest.fixture
def run_hook(hook_path: Path) -> Iterator:
    """Convenience wrapper: tests call `run_hook(payload, env=...)`."""

    def _runner(payload: dict, env: dict[str, str] | None = None) -> tuple[int, str]:
        code, _stdout, stderr = run_hook_subprocess(hook_path, payload, env)
        return code, stderr

    yield _runner


@pytest.fixture
def run_hook_v2(hook_path: Path) -> Iterator:
    """Run hook and return (code, stdout, stderr) for v2 envelope inspection.

    Use when a test needs to assert on the v2 hookSpecificOutput JSON envelope
    emitted on stdout in addition to (or instead of) the v1 stderr text.
    """

    def _runner(
        payload: dict, env: dict[str, str] | None = None
    ) -> tuple[int, str, str]:
        return run_hook_subprocess(hook_path, payload, env)

    yield _runner


@pytest.fixture
def run_as_any_hook(as_any_hook_path: Path) -> Iterator:
    def _runner(payload: dict, env: dict[str, str] | None = None) -> tuple[int, str]:
        code, _stdout, stderr = run_hook_subprocess(as_any_hook_path, payload, env)
        return code, stderr

    yield _runner


@pytest.fixture
def run_console_log_hook(console_log_hook_path: Path) -> Iterator:
    def _runner(payload: dict, env: dict[str, str] | None = None) -> tuple[int, str]:
        code, _stdout, stderr = run_hook_subprocess(console_log_hook_path, payload, env)
        return code, stderr

    yield _runner


def make_write_payload(file_path: str, content: str) -> dict:
    """Build a Write payload (full-file content)."""
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }


def make_edit_payload(file_path: str, new_string: str) -> dict:
    """Build an Edit payload (single fragment)."""
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "new_string": new_string},
    }


def make_multi_edit_payload(file_path: str, edits: list[str]) -> dict:
    """Build a MultiEdit payload (list of fragments)."""
    return {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": file_path,
            "edits": [{"new_string": s} for s in edits],
        },
    }


@pytest.fixture
def make_payload():
    return {
        "write": make_write_payload,
        "edit": make_edit_payload,
        "multi_edit": make_multi_edit_payload,
    }


def parse_v2_envelope(stdout: str) -> dict | None:
    """Parse the v2 `hookSpecificOutput` JSON envelope from stdout.

    Returns the inner `hookSpecificOutput` dict, or None when stdout is empty
    or unparseable. The hook contract says v2 envelopes are emitted as a
    single JSON object on stdout.
    """
    s = (stdout or "").strip()
    if not s:
        return None
    try:
        body = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(body, dict):
        return None
    inner = body.get("hookSpecificOutput")
    if isinstance(inner, dict):
        return inner
    return None


def assert_blocks(
    code: int, stdout: str, stderr: str, *, reason_substring: str = ""
) -> None:
    """Assert v1+v2 dual-emit deny: exit 2, stderr message, v2 deny envelope."""
    assert code == 2, f"expected exit 2, got {code}\nstderr: {stderr}\nstdout: {stdout}"
    assert stderr.strip(), "stderr must carry the v1 reason message"
    if reason_substring:
        assert reason_substring in stderr, (
            f"stderr missing expected substring {reason_substring!r}\nstderr: {stderr}"
        )
    inner = parse_v2_envelope(stdout)
    assert inner is not None, f"v2 envelope missing on stdout: {stdout!r}"
    assert inner.get("permissionDecision") == "deny", (
        f"v2 envelope must set permissionDecision=deny, got: {inner}"
    )
    assert inner.get("permissionDecisionReason"), (
        f"v2 envelope must include a non-empty permissionDecisionReason: {inner}"
    )


def assert_allows(code: int, stdout: str, stderr: str) -> None:
    """Assert plain allow: exit 0, no stderr, no v2 envelope."""
    assert code == 0, f"expected exit 0, got {code}\nstderr: {stderr}\nstdout: {stdout}"


def assert_modifies_input(
    code: int, stdout: str, *, expected_keys: list[str] | None = None
) -> dict:
    """Assert v2 modifiedInput response: exit 0 + envelope with modifiedInput.

    Returns the `modifiedInput` dict so callers can inspect specific fields.
    """
    assert code == 0, f"expected exit 0, got {code}\nstdout: {stdout}"
    inner = parse_v2_envelope(stdout)
    assert inner is not None, f"v2 envelope missing on stdout: {stdout!r}"
    assert inner.get("permissionDecision") == "allow", (
        f"v2 envelope must set permissionDecision=allow, got: {inner}"
    )
    modified = inner.get("modifiedInput")
    assert isinstance(modified, dict), (
        f"v2 envelope must include modifiedInput dict, got: {inner}"
    )
    if expected_keys:
        for key in expected_keys:
            assert key in modified, f"modifiedInput missing key {key!r}: {modified}"
    return modified


def assert_asks(code: int, stderr: str, *, message_substring: str = "") -> None:
    """Assert ask response: exit 1 with a stderr message for the model to read."""
    assert code == 1, f"expected exit 1 (ask), got {code}\nstderr: {stderr}"
    assert stderr.strip(), "ask response must carry a stderr message"
    if message_substring:
        assert message_substring in stderr, (
            f"stderr missing expected ask substring {message_substring!r}\nstderr: {stderr}"
        )


def assert_defers(code: int, stdout: str, stderr: str) -> None:
    """Assert defer response: exit 0, no v2 envelope, empty stderr."""
    assert code == 0, f"expected exit 0 (defer), got {code}\nstderr: {stderr}"
    assert not stderr.strip(), f"defer must produce no stderr, got: {stderr!r}"
    inner = parse_v2_envelope(stdout)
    assert inner is None, f"defer must not emit a v2 envelope, got: {inner}"


def assert_post_context(code: int, stdout: str, *, context_substring: str = "") -> None:
    """Assert PostToolUse additionalContext envelope on stdout."""
    assert code == 0, f"expected exit 0, got {code}\nstdout: {stdout}"
    inner = parse_v2_envelope(stdout)
    assert inner is not None, f"v2 envelope missing on stdout: {stdout!r}"
    assert inner.get("hookEventName") == "PostToolUse", (
        f"PostToolUse envelope expected, got: {inner}"
    )
    ctx = inner.get("additionalContext")
    assert isinstance(ctx, str) and ctx, (
        f"PostToolUse envelope must include additionalContext text: {inner}"
    )
    if context_substring:
        assert context_substring in ctx, (
            f"additionalContext missing substring {context_substring!r}: {ctx}"
        )

from __future__ import annotations
import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
import pytest

pytest.register_assert_rewrite("_helpers.hook_assertions")

from _helpers.cov_env import (  # noqa: E402
    AUDIT_DISABLE_VAR,
    BYPASS_STATE_VAR,
    EMPTY_BYPASS_REGISTRY,
    apply_coverage_env,
)
from _helpers.hook_assertions import HookResult  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "hooks"
SUBPROCESS_TIMEOUT_S = 6.0
SCRATCH_REPO_DIRNAME = "repo"
SCRATCH_README_TEXT = "# Scratch\n"

Payload = dict[str, object]


def _hook_path(name: str) -> Path:
    candidate = name if name.endswith(".py") else f"{name}.py"
    path = HOOKS_DIR / candidate
    if not path.is_file():
        raise FileNotFoundError(f"hook not found: {path}")
    return path


AMBIENT_ISOLATION_VARS = frozenset({AUDIT_DISABLE_VAR, BYPASS_STATE_VAR})


def _build_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    ambient = {
        key: value
        for key, value in os.environ.items()
        if key not in AMBIENT_ISOLATION_VARS
    }
    return apply_coverage_env({**ambient, **(extra or {})})


def _run_hook(
    hook: str | Path,
    payload: Payload,
    env: dict[str, str] | None = None,
    timeout: float = SUBPROCESS_TIMEOUT_S,
) -> HookResult:
    path = hook if isinstance(hook, Path) else _hook_path(hook)
    proc = subprocess.run(
        [sys.executable, str(path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_build_env(env),
        timeout=timeout,
        check=False,
    )
    return HookResult(proc.returncode, proc.stdout, proc.stderr)


@pytest.fixture(scope="session", autouse=True)
def isolate_ambient_hook_state() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(AUDIT_DISABLE_VAR, "1")
        patch.setenv(BYPASS_STATE_VAR, EMPTY_BYPASS_REGISTRY)
        yield


@pytest.fixture
def tool_use() -> Callable[..., Payload]:
    def _build(
        tool_name: str,
        tool_input: Payload | None = None,
        *,
        hook_event_name: str = "PreToolUse",
        cwd: str | None = None,
        session_id: str | None = None,
        transcript_path: str | None = None,
        permission_mode: str | None = None,
        **extra: object,
    ) -> Payload:
        optional = {
            "cwd": cwd,
            "session_id": session_id,
            "transcript_path": transcript_path,
            "permission_mode": permission_mode,
        }
        return {
            "tool_name": tool_name,
            "tool_input": dict(tool_input or {}),
            "hook_event_name": hook_event_name,
            **{key: value for key, value in optional.items() if value is not None},
            **extra,
        }

    return _build


@pytest.fixture
def run_hook() -> Callable[..., HookResult]:
    def _runner(
        hook: str | Path,
        payload: Payload,
        *,
        env: dict[str, str] | None = None,
        timeout: float = SUBPROCESS_TIMEOUT_S,
    ) -> HookResult:
        return _run_hook(hook, payload, env=env, timeout=timeout)

    return _runner


@pytest.fixture(scope="session")
def hooks_dir() -> Path:
    return HOOKS_DIR


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def scratch_repo_root(tmp_path: Path) -> Path:
    root = tmp_path / SCRATCH_REPO_DIRNAME
    root.mkdir()
    (root / "README.md").write_text(SCRATCH_README_TEXT, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=30.0)
    subprocess.run(
        ["git", "-C", str(root), "add", "README.md"], check=True, timeout=30.0
    )
    return root


@pytest.fixture
def repo_scratch(scratch_repo_root: Path) -> Callable[[str, str], Path]:
    def _write(relative: str, text: str) -> Path:
        path = scratch_repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _write

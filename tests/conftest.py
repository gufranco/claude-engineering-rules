from __future__ import annotations
import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
import pytest

pytest.register_assert_rewrite("_helpers.hook_assertions")

from _helpers.hook_assertions import HookResult  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "hooks"
SUBPROCESS_TIMEOUT_S = 6.0
SUBPROCESS_COV_DIR = REPO_ROOT / "tests" / "_subprocess_cov"
EMPTY_BYPASS_REGISTRY = os.devnull
COVERAGERC_PATH = REPO_ROOT / ".coveragerc"


def _hook_path(name: str) -> Path:
    candidate = name if name.endswith(".py") else f"{name}.py"
    path = HOOKS_DIR / candidate
    if not path.is_file():
        raise FileNotFoundError(f"hook not found: {path}")
    return path


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
    env["CLAUDE_BYPASS_STATE"] = EMPTY_BYPASS_REGISTRY
    if _coverage_active():
        env["COVERAGE_PROCESS_START"] = str(COVERAGERC_PATH)
        env["CLAUDE_COVERAGE_ROOT"] = str(REPO_ROOT)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{SUBPROCESS_COV_DIR}{os.pathsep}{existing_pp}"
            if existing_pp
            else str(SUBPROCESS_COV_DIR)
        )
        env.setdefault("COVERAGE_FILE", str(REPO_ROOT / ".coverage"))
        env.setdefault("COVERAGE_CORE", "ctrace")
    if extra:
        env.update(extra)
    return env


def _run_hook(
    hook: str | Path,
    payload: dict[str, Any],
    env: dict[str, str] | None = None,
) -> HookResult:
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
    return HookResult(proc.returncode, proc.stdout, proc.stderr)


@pytest.fixture
def tool_use() -> Callable[..., dict[str, Any]]:
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
def run_hook() -> Callable[..., HookResult]:
    def _runner(
        hook: str | Path,
        payload: dict[str, Any],
        *,
        env: dict[str, str] | None = None,
    ) -> HookResult:
        return _run_hook(hook, payload, env=env)

    return _runner


@pytest.fixture(scope="session")
def hooks_dir() -> Path:
    return HOOKS_DIR


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


def _missing_ancestors(path: Path) -> list[Path]:
    return [parent for parent in path.parents if not parent.exists()]


@pytest.fixture
def repo_scratch() -> Iterator[Callable[[str, str], Path]]:
    created_files: list[Path] = []
    created_dirs: list[Path] = []

    def _write(relative: str, text: str) -> Path:
        path = REPO_ROOT / relative
        created_dirs.extend(_missing_ancestors(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        created_files.append(path)
        return path

    yield _write
    for path in created_files:
        path.unlink(missing_ok=True)
    for directory in created_dirs:
        directory.rmdir()

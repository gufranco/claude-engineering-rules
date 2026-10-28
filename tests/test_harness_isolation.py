from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from coverage.config import read_coverage_config

from _helpers.cov_env import apply_coverage_env
from _helpers.hook_assertions import HookResult, assert_blocked

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.bypass import is_bypassed  # noqa: E402

Payload = dict[str, object]


def _load_conftest() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "harness_conftest", REPO_ROOT / "tests" / "conftest.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load tests/conftest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_env_neutralizes_the_ambient_bypass_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    monkeypatch.setenv("CLAUDE_BYPASS_STATE", str(tmp_path / "ambient.json"))
    conftest = _load_conftest()

    # Act
    env = conftest._build_env()

    # Assert
    assert env["CLAUDE_BYPASS_STATE"] == os.devnull


def test_build_env_neutralizes_an_ambient_audit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("CLAUDE_HOOK_AUDIT_DISABLE", "0")
    conftest = _load_conftest()

    # Act
    env = conftest._build_env()

    # Assert
    assert env["CLAUDE_HOOK_AUDIT_DISABLE"] == "1"


def test_a_test_can_still_point_the_registry_at_its_own_file(tmp_path: Path) -> None:
    # Arrange
    conftest = _load_conftest()
    state = tmp_path / "bypass.json"

    # Act
    env = conftest._build_env({"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert env["CLAUDE_BYPASS_STATE"] == str(state)


def test_the_neutralized_registry_reads_as_empty() -> None:
    # Arrange
    registry = Path(os.devnull)

    # Act
    bypassed = is_bypassed("check-then-act-blocker", state_path=registry)

    # Assert
    assert bypassed is False


def test_a_blocking_hook_still_blocks_under_the_harness(
    tool_use: Callable[..., Payload], run_hook: Callable[..., HookResult]
) -> None:
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": (
                "const existing = await db.seat.findFirst({ where: { showId } });\n"
                "await db.seat.create({ data: { showId } });\n"
            ),
        },
    )

    # Act
    result = run_hook(
        "check-then-act-blocker", payload, env={"CHECK_THEN_ACT_ENFORCE": "1"}
    )

    # Assert
    assert_blocked(result, "read that decides a write")


def test_build_env_anchors_subprocess_coverage_at_the_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("COVERAGE_RUN", "1")
    conftest = _load_conftest()

    # Act
    env = conftest._build_env()

    # Assert
    assert env["CLAUDE_COVERAGE_ROOT"] == str(REPO_ROOT)


def test_apply_coverage_env_anchors_subprocess_coverage_at_the_repository() -> None:
    # Arrange
    base_env: dict[str, str] = {}

    # Act
    env = apply_coverage_env(base_env, force_active=True)

    # Assert
    assert env["CLAUDE_COVERAGE_ROOT"] == str(REPO_ROOT)


def test_coverage_sources_resolve_to_the_repository_from_any_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_COVERAGE_ROOT", str(REPO_ROOT))

    # Act
    sources = read_coverage_config(str(REPO_ROOT / ".coveragerc"), warn=print).source

    # Assert
    assert sources == [
        f"{REPO_ROOT}/hooks",
        f"{REPO_ROOT}/.github/scripts",
        f"{REPO_ROOT}/scripts",
        f"{REPO_ROOT}/tools",
    ]


def test_the_coverage_config_omits_no_hand_written_file() -> None:
    # Arrange
    coveragerc = str(REPO_ROOT / ".coveragerc")

    # Act
    config = read_coverage_config(coveragerc, warn=print)

    # Assert
    assert (config.run_omit, config.report_omit, config.fail_under) == ([], None, 100.0)


def test_a_subprocess_built_from_raw_environ_inherits_the_isolation() -> None:
    # Arrange
    probe = (
        "import os; print(os.environ.get('CLAUDE_HOOK_AUDIT_DISABLE'),"
        " os.environ.get('CLAUDE_BYPASS_STATE'))"
    )

    # Act
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        env={**os.environ},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    # Assert
    assert proc.stdout.split() == ["1", os.devnull]

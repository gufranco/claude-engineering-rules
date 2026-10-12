from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from coverage.config import read_coverage_config

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _helpers.hook_assertions import assert_blocked  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402


def _load_conftest():
    spec = importlib.util.spec_from_file_location(
        "harness_conftest", REPO_ROOT / "tests" / "conftest.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_env_neutralizes_the_ambient_bypass_registry():
    # Arrange
    conftest = _load_conftest()

    # Act
    env = conftest._build_env()

    # Assert
    assert env["CLAUDE_BYPASS_STATE"] == os.devnull


def test_a_test_can_still_point_the_registry_at_its_own_file(tmp_path):
    # Arrange
    conftest = _load_conftest()
    state = tmp_path / "bypass.json"

    # Act
    env = conftest._build_env({"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert env["CLAUDE_BYPASS_STATE"] == str(state)


def test_the_neutralized_registry_reads_as_empty():
    # Arrange
    registry = Path(os.devnull)

    # Act
    bypassed = is_bypassed("check-then-act-blocker", state_path=registry)

    # Assert
    assert bypassed is False


def test_a_blocking_hook_still_blocks_under_the_harness(tool_use, run_hook):
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


def test_build_env_anchors_subprocess_coverage_at_the_repository(monkeypatch):
    # Arrange
    conftest = _load_conftest()
    monkeypatch.setattr(conftest, "_coverage_active", lambda: True)

    # Act
    env = conftest._build_env()

    # Assert
    assert env["CLAUDE_COVERAGE_ROOT"] == str(REPO_ROOT)


def test_apply_coverage_env_anchors_subprocess_coverage_at_the_repository():
    # Arrange
    base_env: dict[str, str] = {}

    # Act
    env = apply_coverage_env(base_env, force_active=True)

    # Assert
    assert env["CLAUDE_COVERAGE_ROOT"] == str(REPO_ROOT)


def test_coverage_sources_resolve_to_the_repository_from_any_directory(
    tmp_path, monkeypatch
):
    # Arrange
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_COVERAGE_ROOT", str(REPO_ROOT))

    # Act
    sources = read_coverage_config(str(REPO_ROOT / ".coveragerc"), warn=print).source

    # Assert
    assert sources == [f"{REPO_ROOT}/hooks", f"{REPO_ROOT}/.github/scripts"]


def test_every_omit_entry_matches_from_any_working_directory():
    # Arrange
    coveragerc = str(REPO_ROOT / ".coveragerc")

    # Act
    omit = read_coverage_config(coveragerc, warn=print).run_omit

    # Assert
    assert [entry for entry in omit if not entry.startswith("*/")] == []

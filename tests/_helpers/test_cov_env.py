from __future__ import annotations

import os
from pathlib import Path

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SUBPROCESS_COV_DIR = REPO_ROOT / "tests" / "_subprocess_cov"


def test_adds_no_coverage_vars_when_inactive(
    monkeypatch: pytest.MonkeyPatch, faker: Faker
) -> None:
    # Arrange
    monkeypatch.delenv("COVERAGE_PROCESS_START", raising=False)
    monkeypatch.delenv("COVERAGE_RUN", raising=False)
    value = faker.word()

    # Act
    result = apply_coverage_env({"FOO": value}, force_active=False)

    # Assert
    assert result == {
        "FOO": value,
        "CLAUDE_HOOK_AUDIT_DISABLE": "1",
        "CLAUDE_BYPASS_STATE": os.devnull,
    }


def test_suppresses_audit_writes_when_active(faker: Faker) -> None:
    # Arrange
    env = {"FOO": faker.word()}

    # Act
    result = apply_coverage_env(env, force_active=True)

    # Assert
    assert result["CLAUDE_HOOK_AUDIT_DISABLE"] == "1"


def test_keeps_an_audit_setting_the_caller_chose() -> None:
    # Arrange
    env = {"CLAUDE_HOOK_AUDIT_DISABLE": "0"}

    # Act
    result = apply_coverage_env(env, force_active=False)

    # Assert
    assert result["CLAUDE_HOOK_AUDIT_DISABLE"] == "0"


def test_points_the_bypass_registry_at_an_empty_source_by_default() -> None:
    # Arrange
    env: dict[str, str] = {}

    # Act
    result = apply_coverage_env(env, force_active=True)

    # Assert
    assert result["CLAUDE_BYPASS_STATE"] == os.devnull


def test_keeps_a_bypass_registry_the_caller_chose(tmp_path: Path) -> None:
    # Arrange
    state = str(tmp_path / "bypass.json")

    # Act
    result = apply_coverage_env({"CLAUDE_BYPASS_STATE": state}, force_active=False)

    # Assert
    assert result["CLAUDE_BYPASS_STATE"] == state


def test_does_not_mutate_caller_env(faker: Faker) -> None:
    # Arrange
    value = faker.word()
    base = {"FOO": value}

    # Act
    apply_coverage_env(base, force_active=True)

    # Assert
    assert base == {"FOO": value}


def test_adds_coverage_env_when_active(faker: Faker) -> None:
    # Arrange
    value = faker.word()

    # Act
    result = apply_coverage_env({"FOO": value}, force_active=True)

    # Assert
    assert result["FOO"] == value
    assert result["COVERAGE_PROCESS_START"] == str(REPO_ROOT / ".coveragerc")
    assert result["PYTHONPATH"] == str(SUBPROCESS_COV_DIR)
    assert result["COVERAGE_FILE"] == str(REPO_ROOT / ".coverage")


def test_keeps_a_coverage_file_the_caller_chose(tmp_path: Path) -> None:
    # Arrange
    data_file = str(tmp_path / ".coverage")

    # Act
    result = apply_coverage_env({"COVERAGE_FILE": data_file}, force_active=True)

    # Assert
    assert result["COVERAGE_FILE"] == data_file


def test_prepends_the_hook_dir_to_an_existing_pythonpath(faker: Faker) -> None:
    # Arrange
    existing = f"/{faker.word()}/{faker.word()}"

    # Act
    result = apply_coverage_env({"PYTHONPATH": existing}, force_active=True)

    # Assert
    assert result["PYTHONPATH"] == f"{SUBPROCESS_COV_DIR}{os.pathsep}{existing}"

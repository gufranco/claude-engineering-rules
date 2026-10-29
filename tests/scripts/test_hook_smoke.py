from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "hook-smoke.py"
ALWAYS_ALLOWS = {
    "section": "English-Only Reminder",
    "hook": "english-only-reminder.py",
    "fixture": "english-only-reminder.json",
}


@pytest.fixture
def smoke() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hook_smoke", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def work(smoke: ModuleType, tmp_path: Path) -> Path:
    smoke.prepare(tmp_path)
    return tmp_path


def test_the_suite_reports_each_verdict_and_fails_on_a_mismatch(
    smoke: ModuleType, work: Path, faker: Faker, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    passing, failing = faker.sentence(), faker.sentence()
    cases = [
        smoke.Case(description=passing, expect=0, **ALWAYS_ALLOWS),
        smoke.Case(description=failing, expect=2, **ALWAYS_ALLOWS),
    ]

    # Act
    code = smoke.run_suite(cases, work)

    # Assert
    assert (code, capsys.readouterr().out) == (
        1,
        "\n=== English-Only Reminder ===\n"
        f"  PASS: {passing} (exit 0)\n"
        f"  FAIL: {failing} (expected exit 2, got 0)\n"
        "\n=== Results ===\n  Passed: 1\n  Failed: 1\n\n",
    )


def test_a_case_file_entry_takes_the_default_directory_and_environment(
    smoke: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    description = faker.sentence()
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps([{**ALWAYS_ALLOWS, "description": description, "expect": 0}])
    )

    # Act
    cases = smoke.load_cases(path)

    # Assert
    assert cases == [
        smoke.Case(
            description=description,
            expect=0,
            render=False,
            cwd="cwd",
            env={},
            **ALWAYS_ALLOWS,
        )
    ]


def test_a_rendered_fixture_points_at_the_work_directory(
    smoke: ModuleType, work: Path
) -> None:
    # Arrange
    case = smoke.Case(
        section="Git Author Guard",
        description="rendered",
        hook="git-author-guard.py",
        fixture="bash-git-commit-local-override.json",
        expect=2,
        render=True,
    )

    # Act
    payload = smoke.case_input(case, work).decode()

    # Assert
    assert (smoke.PLACEHOLDER in payload, str(work / "local-override") in payload) == (
        False,
        True,
    )


def test_an_unrendered_fixture_is_passed_through_unchanged(
    smoke: ModuleType, work: Path
) -> None:
    # Arrange
    case = smoke.Case(description="raw", expect=0, **ALWAYS_ALLOWS)

    # Act
    payload = smoke.case_input(case, work)

    # Assert
    assert payload == (smoke.FIXTURES_DIR / ALWAYS_ALLOWS["fixture"]).read_bytes()


def test_case_environment_isolates_the_hook_and_expands_the_work_directory(
    smoke: ModuleType, work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.delenv("CLAUDE_HOOK_AUDIT_DISABLE", raising=False)
    monkeypatch.delenv("CLAUDE_BYPASS_STATE", raising=False)
    case = smoke.Case(
        description="env",
        expect=0,
        env={"HOME": "@WORK_DIR@/no-identity"},
        **ALWAYS_ALLOWS,
    )

    # Act
    env = smoke.case_env(case, work)

    # Assert
    assert (
        env["CLAUDE_HOOK_AUDIT_DISABLE"],
        env["CLAUDE_BYPASS_STATE"],
        env["HOME"],
    ) == (
        "1",
        os.devnull,
        str(work / "no-identity"),
    )


def git_output(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def test_preparation_stages_the_secret_and_records_the_placeholder_author(
    smoke: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    work = tmp_path / "fresh"
    work.mkdir()

    # Act
    smoke.prepare(work)

    # Assert
    assert (
        git_output("diff", "--cached", "--name-only", cwd=work / "staged-secret"),
        git_output("log", "-1", "--format=%ae", cwd=work / "placeholder-commit"),
        (work / "resolved-home" / ".gitconfig").is_file(),
    ) == ("settings.ini\n", "placeholder@example.com\n", True)


def test_the_script_runs_as_a_program(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    description = faker.sentence()
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps([{**ALWAYS_ALLOWS, "description": description, "expect": 0}])
    )
    env = apply_coverage_env(dict(os.environ))

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--cases", str(cases)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stdout) == (
        0,
        "\n=== English-Only Reminder ===\n"
        f"  PASS: {description} (exit 0)\n"
        "\n=== Results ===\n  Passed: 1\n  Failed: 0\n\n",
    )

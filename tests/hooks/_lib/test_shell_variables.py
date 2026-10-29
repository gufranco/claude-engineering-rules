from __future__ import annotations

import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.shell_variables import assignments, expand  # noqa: E402

fake = Faker()
Faker.seed(4417)


@pytest.mark.parametrize("template", ["$S/body.md", "${S}/body.md"])
def test_a_known_variable_expands_in_both_spellings(template):
    # Arrange
    folder = f"/tmp/{fake.word()}"

    # Act
    result = expand(template, {"S": folder})

    # Assert
    assert result == f"{folder}/body.md"


def test_an_environment_variable_fills_in_when_the_command_never_set_it(monkeypatch):
    # Arrange
    folder = f"/srv/{fake.word()}"
    monkeypatch.setenv("SHOTS_DIR", folder)

    # Act
    result = expand("$SHOTS_DIR/after.png", {})

    # Assert
    assert result == f"{folder}/after.png"


def test_an_unknown_variable_is_left_for_the_caller_to_report(monkeypatch):
    # Arrange
    monkeypatch.delenv("NEVER_SET_ANYWHERE", raising=False)

    # Act
    result = expand("$NEVER_SET_ANYWHERE/after.png", {})

    # Assert
    assert result == "$NEVER_SET_ANYWHERE/after.png"


def test_a_home_prefix_expands(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("HOME", str(tmp_path))

    # Act
    result = expand("~/after.png", {})

    # Assert
    assert result == f"{tmp_path}/after.png"


@pytest.mark.parametrize(
    ("segment", "expected"),
    [
        (["S=/a"], {"S": "/a"}),
        (["export", "E=$S/even"], {"S": "/a", "E": "/a/even"}),
        (["A=1", "B=2"], {"S": "/a", "A": "1", "B": "2"}),
    ],
)
def test_an_assignment_segment_extends_the_known_variables(segment, expected):
    # Arrange
    known = {"S": "/a"}

    # Act
    result = assignments(segment, known)

    # Assert
    assert result == {**known, **expected}


@pytest.mark.parametrize(
    "segment", [["gh", "pr", "edit"], ["GH_TOKEN=x", "gh", "pr"], ["export"], []]
)
def test_a_segment_that_runs_a_command_is_not_an_assignment(segment):
    # Arrange
    known: dict[str, str] = {}

    # Act
    result = assignments(segment, known)

    # Assert
    assert result is None

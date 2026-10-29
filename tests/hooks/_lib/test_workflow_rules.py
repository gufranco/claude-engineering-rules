from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.workflow_rules import find, is_workflow  # noqa: E402

PINNED = "a" * 40

CLEAN = f"""name: CI
on:
  push:
    branches: [main]
  pull_request:
concurrency:
  group: ci-${{{{ github.ref }}}}
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-26.04
    steps:
      - uses: step-security/harden-runner@{PINNED} # v2.22.3
        with:
          egress-policy: audit
      - uses: actions/checkout@v6
      - uses: ./.github/actions/setup
      - name: npm is not used here
        run: corepack pnpm install --frozen-lockfile
      - run: uv sync --locked && uv pip install -e .
"""


def _messages(text: str, full_file: bool = True) -> list[tuple[int, str, bool]]:
    return [
        (hit.line, hit.message, hit.blocking)
        for hit in find(".github/workflows/ci.yml", text, full_file)
    ]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/repo/.github/workflows/ci.yml", True),
        (".github/workflows/release.yaml", True),
        ("/repo/.github/actions/setup/action.yml", False),
        ("/repo/workflows/ci.yml", False),
    ],
)
def test_only_workflow_files_are_checked(path, expected):
    # Arrange
    candidate = path

    # Act
    result = is_workflow(candidate)

    # Assert
    assert result is expected


def test_a_workflow_following_every_default_has_no_findings():
    # Arrange
    text = CLEAN

    # Act
    result = _messages(text)

    # Assert
    assert result == []


@pytest.mark.parametrize(
    ("label", "fragment"),
    [
        ("macos-15", "macOS runner"),
        ("[macos-26, ubuntu-26.04]", "macOS runner"),
        ("ubuntu-latest", "moving label"),
        ("windows-latest", "moving label"),
    ],
)
def test_macos_and_latest_runner_labels_block(label, fragment):
    # Arrange
    text = CLEAN.replace("runs-on: ubuntu-26.04", f"runs-on: {label}")

    # Act
    result = _messages(text)

    # Assert
    assert len(result) == 1
    assert result[0][0] == 11
    assert fragment in result[0][1]
    assert result[0][2] is True


def test_an_older_ubuntu_lts_label_is_advisory():
    # Arrange
    text = CLEAN.replace("ubuntu-26.04", "ubuntu-24.04")

    # Act
    result = _messages(text)

    # Assert
    assert result == [
        (11, "runs-on: ubuntu-24.04 is older than ubuntu-26.04, the newest LTS", False)
    ]


@pytest.mark.parametrize(
    "uses",
    ["step-security/harden-runner@v2", "astral-sh/setup-uv@main"],
)
def test_a_third_party_action_on_a_tag_or_branch_blocks(uses):
    # Arrange
    text = CLEAN.replace(f"step-security/harden-runner@{PINNED} # v2.22.3", uses)

    # Act
    result = _messages(text)

    # Assert
    blocking = [(line, message) for line, message, blocks in result if blocks]
    assert len(blocking) == 1
    assert blocking[0][0] == 13
    assert "full 40-character commit SHA" in blocking[0][1]


@pytest.mark.parametrize(
    "command",
    [
        "npm ci",
        "npx semantic-release",
        "yarn install",
        "pip install -r requirements.txt",
        "python -m pip install ruff",
    ],
)
def test_npm_npx_yarn_and_pip_in_a_run_step_block(command):
    # Arrange
    text = CLEAN.replace("corepack pnpm install --frozen-lockfile", command)

    # Act
    result = _messages(text)

    # Assert
    assert len(result) == 1
    assert result[0][0] == 19
    assert "pnpm or uv" in result[0][1]


def test_a_multiline_run_block_is_checked_line_by_line():
    # Arrange
    text = CLEAN.replace(
        "        run: corepack pnpm install --frozen-lockfile",
        "        run: |\n          echo start\n          npm install",
    )

    # Act
    result = _messages(text)

    # Assert
    assert [(line, blocking) for line, _message, blocking in result] == [(21, True)]


def test_a_push_workflow_without_concurrency_blocks():
    # Arrange
    text = CLEAN.replace(
        "concurrency:\n  group: ci-${{ github.ref }}\n  cancel-in-progress: true\n", ""
    )

    # Act
    result = _messages(text)

    # Assert
    assert result == [
        (
            1,
            "no concurrency group with cancel-in-progress, so a new push leaves "
            "the superseded run going",
            True,
        )
    ]


def test_a_reusable_workflow_needs_no_concurrency_group():
    # Arrange
    text = CLEAN.replace(
        "concurrency:\n  group: ci-${{ github.ref }}\n  cancel-in-progress: true\n", ""
    ).replace(
        "on:\n  push:\n    branches: [main]\n  pull_request:\n",
        "on:\n  workflow_call:\n",
    )

    # Act
    result = _messages(text)

    # Assert
    assert result == []


def test_a_job_without_harden_runner_is_advisory():
    # Arrange
    text = CLEAN + (
        "  lint:\n    runs-on: ubuntu-26.04\n    steps:\n      - uses: actions/checkout@v6\n"
    )

    # Act
    result = _messages(text)

    # Assert
    assert result == [
        (
            1,
            "2 jobs run steps and 1 starts with step-security/harden-runner",
            False,
        )
    ]


def test_an_edit_fragment_skips_the_whole_file_checks():
    # Arrange
    fragment = "    runs-on: ubuntu-26.04\n    steps:\n      - run: echo ok\n"

    # Act
    result = _messages(fragment, full_file=False)

    # Assert
    assert result == []


def test_a_file_outside_the_workflows_folder_has_no_findings():
    # Arrange
    text = CLEAN.replace("ubuntu-26.04", "macos-15")

    # Act
    result = find(".github/actions/setup/action.yml", text, True)

    # Assert
    assert result == ()

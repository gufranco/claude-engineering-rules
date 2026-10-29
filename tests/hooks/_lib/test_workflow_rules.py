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


@pytest.mark.parametrize("label", ["ubuntu-latest", "windows-latest", "macos-latest"])
def test_latest_runner_labels_block(label):
    # Arrange
    text = CLEAN.replace("runs-on: ubuntu-26.04", f"runs-on: {label}")

    # Act
    result = _messages(text)

    # Assert
    assert len(result) == 1
    assert result[0][0] == 11
    assert "moving label" in result[0][1]
    assert result[0][2] is True


@pytest.mark.parametrize("label", ["macos-15", "[macos-26, ubuntu-26.04]"])
def test_a_macos_runner_with_no_macos_only_tool_is_advisory(label):
    # Arrange
    text = CLEAN.replace("runs-on: ubuntu-26.04", f"runs-on: {label}")

    # Act
    result = _messages(text)

    # Assert
    assert result == [
        (
            11,
            "runs-on names a macOS runner, which is slow and costly; keep it only "
            "for a job that needs macOS, and run everything else on ubuntu-26.04",
            False,
        )
    ]


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
            "no top-level concurrency group with cancel-in-progress, so a new push "
            "leaves the superseded run going; a job that must finish, such as a "
            "release, belongs in its own workflow",
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


def _on(triggers: str, cancel: str = "true") -> str:
    return CLEAN.replace(
        "on:\n  push:\n    branches: [main]\n  pull_request:\n", triggers
    ).replace("cancel-in-progress: true", f"cancel-in-progress: {cancel}")


@pytest.mark.parametrize(
    "path",
    [
        "/work/homebrew-tap/.github/workflows/ci.yml",
        "homebrew-core/.github/workflows/tests.yaml",
    ],
)
def test_a_homebrew_tap_may_run_on_macos(path):
    # Arrange
    text = CLEAN.replace("ubuntu-26.04", "macos-15")

    # Act
    result = find(path, text, True)

    # Assert
    assert result == ()


@pytest.mark.parametrize(
    "step",
    [
        f"      - uses: Homebrew/actions/setup-homebrew@{PINNED}\n",
        "      - run: xcodebuild -scheme App test\n",
        "      - run: hdiutil create -size 1m disk.dmg\n",
        "      - run: brew install --formula bash\n",
    ],
)
def test_a_workflow_using_a_macos_only_tool_may_run_on_macos(step):
    # Arrange
    text = CLEAN.replace("ubuntu-26.04", "macos-15").replace(
        "      - uses: actions/checkout@v6\n",
        f"      - uses: actions/checkout@v6\n{step}",
    )

    # Act
    result = _messages(text)

    # Assert
    assert result == []


def test_a_homebrew_tap_still_blocks_a_moving_macos_label():
    # Arrange
    text = CLEAN.replace("ubuntu-26.04", "macos-latest")

    # Act
    result = find("/work/homebrew-tap/.github/workflows/ci.yml", text, True)

    # Assert
    assert [(hit.line, hit.blocking) for hit in result] == [(11, True)]
    assert "moving label" in result[0].message


@pytest.mark.parametrize(
    "triggers",
    [
        "on:\n  push:\n    tags: ['v*']\n",
        "on:\n  workflow_run:\n    workflows: [CI]\n    types: [completed]\n",
        "on:\n  release:\n    types: [published]\n",
        "on:\n  repository_dispatch:\n    types: [formula-bump]\n",
    ],
)
def test_a_release_workflow_that_never_cancels_passes(triggers):
    # Arrange
    text = _on(triggers, cancel="false")

    # Act
    result = _messages(text)

    # Assert
    assert result == []


@pytest.mark.parametrize(
    "triggers",
    [
        "on:\n  push:\n    tags-ignore: ['nightly']\n",
        "on: [workflow_run]\n",
    ],
)
def test_a_release_workflow_that_cancels_in_progress_blocks(triggers):
    # Arrange
    text = _on(triggers)

    # Act
    result = _messages(text)

    # Assert
    assert result == [
        (
            1,
            "a release workflow sets cancel-in-progress: true, so a newer run stops "
            "a release halfway; set cancel-in-progress: false",
            True,
        )
    ]


@pytest.mark.parametrize(
    "triggers",
    [
        "on:\n  pull_request:\n  release:\n    types: [published]\n",
        "on:\n  push:\n    branches: [main]\n  workflow_run:\n    workflows: [CI]\n",
    ],
)
def test_a_workflow_that_checks_pushes_and_releases_blocks(triggers):
    # Arrange
    text = _on(triggers)

    # Act
    result = _messages(text)

    # Assert
    assert result == [
        (
            1,
            "this workflow checks pushes and also releases, so cancelling superseded "
            "runs stops a release halfway; move the release to its own workflow on "
            "workflow_run, release, repository_dispatch or a tag push",
            True,
        )
    ]


@pytest.mark.parametrize("triggers", ["on: push\n", "on:\n  push:\n"])
def test_an_unfiltered_push_needs_a_cancelling_group(triggers):
    # Arrange
    text = _on(triggers, cancel="false")

    # Act
    result = _messages(text)

    # Assert
    assert [(line, blocking) for line, _message, blocking in result] == [(1, True)]
    assert "no top-level concurrency group" in result[0][1]


@pytest.mark.parametrize(
    "triggers",
    [
        "on:\n  schedule:\n    - cron: '17 6 * * 1'\n  # weekly\n\n  workflow_dispatch:\n",
        "",
    ],
)
def test_a_scheduled_or_triggerless_workflow_may_cancel_or_not(triggers):
    # Arrange
    texts = [_on(triggers), _on(triggers, cancel="false")]

    # Act
    result = [_messages(text) for text in texts]

    # Assert
    assert result == [[], []]


def test_a_file_outside_the_workflows_folder_has_no_findings():
    # Arrange
    text = CLEAN.replace("ubuntu-26.04", "macos-15")

    # Act
    result = find(".github/actions/setup/action.yml", text, True)

    # Assert
    assert result == ()

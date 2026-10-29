from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "workflow-guard"
PATH = "/repo/.github/workflows/ci.yml"
PINNED = "b" * 40

WORKFLOW = f"""name: CI
on: [push, pull_request]
concurrency:
  group: ci-${{{{ github.ref }}}}
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-26.04
    steps:
      - uses: step-security/harden-runner@{PINNED} # v2.22.3
      - uses: actions/checkout@v6
      - run: corepack pnpm install --frozen-lockfile
"""


def test_a_workflow_on_a_moving_label_is_blocked(tool_use, run_hook):
    # Arrange
    content = WORKFLOW.replace("ubuntu-26.04", "macos-latest")
    payload = tool_use("Write", {"file_path": PATH, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "moving label")
    assert "WORKFLOW_GUARD_DISABLE" in stderr


def test_a_macos_workflow_without_a_macos_only_tool_only_warns(tool_use, run_hook):
    # Arrange
    content = WORKFLOW.replace("ubuntu-26.04", "macos-15")
    payload = tool_use("Write", {"file_path": PATH, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    assert "keep it only for a job that needs macOS" in result.stdout + result.stderr


def test_an_edit_adding_npx_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": PATH,
            "old_string": "corepack pnpm install --frozen-lockfile",
            "new_string": "npx semantic-release",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "use pnpm or uv")


def test_an_older_lts_only_warns(tool_use, run_hook):
    # Arrange
    content = WORKFLOW.replace("ubuntu-26.04", "ubuntu-24.04")
    payload = tool_use("Write", {"file_path": PATH, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    assert "older than ubuntu-26.04" in result.stdout + result.stderr


def test_a_compliant_workflow_and_other_files_pass_silently(tool_use, run_hook):
    # Arrange
    payloads = [
        tool_use("Write", {"file_path": PATH, "content": WORKFLOW}),
        tool_use(
            "Write",
            {"file_path": "/repo/docs/ci.yml", "content": "runs-on: macos-15\n"},
        ),
    ]

    # Act
    results = [run_hook(HOOK, payload) for payload in payloads]

    # Assert
    assert [(r.code, r.stdout, r.stderr) for r in results] == [(0, "", "")] * 2


def test_a_homebrew_tap_workflow_on_macos_passes(tool_use, run_hook):
    # Arrange
    content = WORKFLOW.replace("ubuntu-26.04", "macos-15")
    path = "/repo/homebrew-tap/.github/workflows/ci.yml"
    payload = tool_use("Write", {"file_path": path, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert (result.code, result.stdout, result.stderr) == (0, "", "")


def test_a_release_workflow_that_cancels_in_progress_is_blocked(tool_use, run_hook):
    # Arrange
    content = WORKFLOW.replace("on: [push, pull_request]", "on: [workflow_run]")
    payload = tool_use("Write", {"file_path": PATH, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "stops a release halfway")


def test_the_disable_variable_lets_a_blocked_workflow_through(tool_use, run_hook):
    # Arrange
    content = WORKFLOW.replace("ubuntu-26.04", "ubuntu-latest")
    payload = tool_use("Write", {"file_path": PATH, "content": content})

    # Act
    result = run_hook(HOOK, payload, env={"WORKFLOW_GUARD_DISABLE": "1"})

    # Assert
    assert (result.code, result.stderr) == (0, "")

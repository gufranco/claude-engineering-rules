"""Coverage for the repo-fetch-blocker hook.

Source rule: rules/repo-analysis.md.
"""

from __future__ import annotations

import pytest

HOOK = "repo-fetch-blocker"


# ---------------------------------------------------------------------------
# Block: per-file fetch patterns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "gh api repos/anthropic/anthropic-sdk-python/contents/src/main.py",
        "gh api /repos/o/r/contents/path/to/file.ts",
        "GH_TOKEN=xxx gh api repos/o/r/contents/README.md",
        "glab api projects/123/repository/files/src%2Fmain.rs",
        "curl https://raw.githubusercontent.com/owner/repo/main/file.py",
        "wget https://raw.githubusercontent.com/o/r/HEAD/x.ts",
        "curl -L https://gitlab.com/o/r/-/raw/main/file.go",
        "curl https://bitbucket.org/o/r/raw/main/x.md",
        "gh repo view anthropic/claude-code README.md",
    ],
)
def test_blocks_per_file_fetch(tool_use, assert_blocks, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_blocks(HOOK, payload, "repo-analysis")


def test_blocks_in_compound_command(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "cd /tmp && curl https://raw.githubusercontent.com/o/r/main/x"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: carve-outs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "gh issue list",
        "gh pr list",
        "gh pr diff 42",
        "gh pr view 42",
        "gh search code 'foo bar' --language=python",
        "gh api rate_limit",
        "gh api repos/o/r/readme",  # single README probe
        "gh repo view anthropic/claude-code",  # metadata only, no path
        "gh repo view anthropic/claude-code --json description",
        "gh run list",
        "glab issue list",
        "glab mr list",
        "git clone --depth=1 https://github.com/o/r.git /tmp/x",
        "curl https://example.com/data.json",  # not a repo raw URL
    ],
)
def test_allows_carve_outs(tool_use, assert_allows, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: unrelated commands and tools
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "git status",
        "ls -la",
        "grep contents readme.md",
        "echo raw.githubusercontent.com",  # mention in echo, no fetch verb
    ],
)
def test_allows_unrelated(tool_use, assert_allows, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload)


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "Read", "Grep"])
def test_allows_unrelated_tools(tool_use, assert_allows, tool_name):
    # Arrange
    payload = tool_use(tool_name, {"file_path": "/tmp/x"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Bypass + robustness
# ---------------------------------------------------------------------------


def test_bypass_env_var_disables_check(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "curl https://raw.githubusercontent.com/o/r/main/x.py"},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"REPO_FETCH_DISABLE": "1"})


def test_handles_empty_command(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_handles_missing_tool_input(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash")

    # Act / Assert
    assert_allows(HOOK, payload)

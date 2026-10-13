from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "repo-fetch-blocker"


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
def test_blocks_per_file_fetch(tool_use, run_hook, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "repo-analysis")


def test_blocks_in_compound_command(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "cd /tmp && curl https://raw.githubusercontent.com/o/r/main/x"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result, "BLOCKED: curl/wget against raw.githubusercontent.com (or equivalent)."
    )


@pytest.mark.parametrize(
    "cmd",
    [
        "gh issue list",
        "gh pr list",
        "gh pr diff 42",
        "gh pr view 42",
        "gh search code 'foo bar' --language=python",
        "gh api rate_limit",
        "gh api repos/o/r/readme",
        "gh repo view anthropic/claude-code",
        "gh repo view anthropic/claude-code --json description",
        "gh run list",
        "glab issue list",
        "glab mr list",
        "git clone --depth=1 https://github.com/o/r.git /tmp/x",
        "curl https://example.com/data.json",
    ],
)
def test_allows_carve_outs(tool_use, run_hook, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "cmd",
    [
        "git status",
        "ls -la",
        "grep contents readme.md",
        "echo raw.githubusercontent.com",
    ],
)
def test_allows_unrelated(tool_use, run_hook, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "Read", "Grep"])
def test_allows_unrelated_tools(tool_use, run_hook, tool_name):
    # Arrange
    payload = tool_use(tool_name, {"file_path": "/tmp/x"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_var_disables_check(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "curl https://raw.githubusercontent.com/o/r/main/x.py"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"REPO_FETCH_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_handles_empty_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_handles_missing_tool_input(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash")

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


RAW_FETCH = "curl https://raw.githubusercontent.com/o/r/main/x"


def test_the_private_repo_advice_keeps_the_token_out_of_the_url(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": RAW_FETCH})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    message = result.stdout + result.stderr
    assert ("@github.com" in message, "credential." in message) == (False, True)


def test_a_fetch_named_inside_a_heredoc_body_is_data(tool_use, run_hook):
    # Arrange
    command = "cat >> notes.md <<'EOF'\n" + RAW_FETCH + "\nEOF"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)

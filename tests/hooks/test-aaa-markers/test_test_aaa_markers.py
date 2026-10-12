from __future__ import annotations

import subprocess
import os
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))

from git_repo_fixture import GitRepo, new_git_repo  # noqa: E402

HOOK = "test-aaa-markers"
BLOCK_MSG = "BLOCKED by test-aaa-markers"
GOOD = (
    "def test_a():\n"
    "    # Arrange\n"
    "    x = 1\n"
    "\n"
    "    # Act\n"
    "    y = x + 1\n"
    "\n"
    "    # Assert\n"
    "    assert y == 2\n"
)
MISSING_ACT = GOOD.replace("    # Act\n", "")


@pytest.fixture
def repo(tmp_path: Path) -> GitRepo:
    return new_git_repo(tmp_path)


def test_blocks_a_written_test_without_markers(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/tests/test_a.py", "content": MISSING_ACT}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "test_a (line 1): missing Act" in stderr


def test_allows_a_well_formed_written_test(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/tests/test_a.py", "content": GOOD})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_allows_an_edit_that_leaves_legacy_tests_untouched(
    tool_use, run_hook, tmp_path
):
    # Arrange
    path = tmp_path / "tests" / "test_a.py"
    path.parent.mkdir()
    path.write_text("def test_old():\n    assert True\n\n\nX = 1\n", encoding="utf-8")
    payload = tool_use(
        "Edit",
        {"file_path": str(path), "old_string": "X = 1\n", "new_string": "X = 2\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_blocks_a_multiedit_that_changes_a_legacy_test(tool_use, run_hook, tmp_path):
    # Arrange
    path = tmp_path / "tests" / "test_a.py"
    path.parent.mkdir()
    path.write_text("def test_old():\n    assert True\n", encoding="utf-8")
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": str(path),
            "edits": [{"old_string": "True", "new_string": "1 == 1"}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "test_old (line 1)" in stderr


@pytest.mark.parametrize(
    ("file_path", "content"),
    [
        ("/repo/src/a.test.ts", "it('x', () => {\n  expect(1).toBe(1)\n})\n"),
        ("/repo/pkg/a_test.go", "func TestA(t *testing.T) {\n\tt.Log(1)\n}\n"),
        ("/repo/tests/a.bats", '@test "a" {\n  true\n}\n'),
    ],
)
def test_blocks_a_test_without_markers_in_each_language(
    tool_use, run_hook, file_path, content
):
    # Arrange
    payload = tool_use("Write", {"file_path": file_path, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "missing Arrange, Act, Assert" in stderr


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Write", {"file_path": "/repo/src/app.py", "content": MISSING_ACT}),
        ("Write", {"file_path": "/repo/spec/a_spec.rb", "content": "it 'x' do\nend\n"}),
        (
            "Edit",
            {
                "file_path": "/repo/tests/test_gone.py",
                "old_string": "a",
                "new_string": "b",
            },
        ),
        ("Read", {"file_path": "/repo/tests/test_a.py"}),
    ],
)
def test_allows_a_payload_it_does_not_enforce(tool_use, run_hook, tool, tool_input):
    # Arrange
    payload = tool_use(tool, tool_input)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_blocks_a_malformed_test_staged_through_bash(tool_use, run_hook, repo):
    # Arrange
    repo.stage("tests/test_a.py", MISSING_ACT)
    payload = tool_use("Bash", {"command": "git commit -m x"}, cwd=str(repo.root))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "tests/test_a.py" in stderr


def test_allows_a_well_formed_test_staged_through_bash(tool_use, run_hook, repo):
    # Arrange
    repo.stage("tests/test_a.py", GOOD)
    payload = tool_use("Bash", {"command": "git commit -m x"}, cwd=str(repo.root))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_fails_closed_when_the_index_cannot_be_read(tool_use, run_hook, repo):
    # Arrange
    broken = repo.root / "broken-index"
    broken.write_bytes(b"not an index")
    payload = tool_use("Bash", {"command": "git commit -m x"}, cwd=str(repo.root))

    # Act
    result = run_hook(HOOK, payload, env={"GIT_INDEX_FILE": str(broken)})

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "could not read the staged files" in stderr


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_name": "Bash", "tool_input": {"command": 5}},
        {"tool_name": "Write", "tool_input": "x"},
    ],
)
def test_allows_a_payload_with_nothing_to_check(run_hook, payload):
    # Arrange
    candidate = payload

    # Act
    result = run_hook(HOOK, candidate)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_allows_everything_when_bypassed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/tests/test_a.py", "content": MISSING_ACT}
    )

    # Act
    result = run_hook(HOOK, payload, env={"TEST_AAA_MARKERS_DISABLE": "1"})

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


@pytest.mark.parametrize(
    "env",
    [{"CLAUDE_HOOK_PROFILE": "minimal"}, {"CLAUDE_DISABLED_HOOKS": "test-aaa-markers"}],
)
def test_allows_when_the_profile_skips_the_hook(tool_use, run_hook, env):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/tests/test_a.py",
            "content": "# explain\ndef test_a():\n    pass\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_allows_a_bash_command_without_a_commit(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "ls"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


@pytest.mark.parametrize("raw", ["not json", '["not", "an", "object"]', ""])
def test_blocks_input_it_cannot_read(raw, hooks_dir):
    # Arrange
    hook = hooks_dir / "test-aaa-markers.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=raw,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_BYPASS_STATE": os.devnull},
        check=False,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr

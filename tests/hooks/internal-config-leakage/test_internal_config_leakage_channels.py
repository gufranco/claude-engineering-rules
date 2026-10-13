from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

ROOT = Path(__file__).resolve().parents[3]
HOOK = "internal-config-leakage"
HOOK_PATH = ROOT / "hooks" / f"{HOOK}.py"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tests"))

from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _lib.bypass_writer import set_bypass  # noqa: E402

LEAK = "see " + "rules/" + "testing.md"
DOC = "/tmp/project/notes.md"
PAYLOAD_JSON = "/tmp/project/payload.json"


@pytest.fixture(scope="module")
def hook():
    spec = importlib.util.spec_from_file_location("_icl_channels", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_an_empty_command_does_not_publish(hook):
    # Arrange
    cmd = ""

    # Act
    publishes = hook.is_publishing_bash(cmd)

    # Assert
    assert publishes is False


def test_an_empty_command_does_not_author_a_git_message(hook):
    # Arrange
    cmd = ""

    # Act
    authors = hook.is_git_message_bash(cmd)

    # Assert
    assert authors is False


def test_an_unterminated_heredoc_keeps_its_body(hook):
    # Arrange
    cmd = "git commit -F - <<EOF\nline one\nline two"

    # Act
    bodies, remainder = hook.split_heredoc_bodies(cmd)

    # Assert
    assert (bodies, remainder) == (["line one\nline two"], "git commit -F - <<EOF")


def test_a_heredoc_for_another_command_is_not_a_message_body(hook):
    # Arrange
    cmd = "cat <<EOF\nline one\nEOF"

    # Act
    bodies, remainder = hook.split_heredoc_bodies(cmd)

    # Assert
    assert (bodies, remainder) == ([], "cat <<EOF")


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git commit -m 'unterminated", None),
        ("git commit", None),
        ("git commit -m", []),
        ("git commit --message='fix: y'", ["fix: y"]),
    ],
)
def test_git_message_extraction(hook, command, expected):
    # Arrange
    command_input = command

    # Act
    texts = hook.extract_git_message_texts(command_input)

    # Assert
    assert texts == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("", False),
        ("not json", False),
        ("{bad", False),
        ("{} ", False),
        ('{"comments": [], "commit_id": "abc"}', True),
        ('{"body": "text"}', True),
        ('{"title": "t", "head": "feat"}', True),
        ('{"title": "t"}', False),
    ],
)
def test_publishing_json_detection(hook, content, expected):
    # Arrange
    content_input = content

    # Act
    looks = hook.looks_like_publishing_json(content_input)

    # Assert
    assert looks is expected


def test_a_json_array_is_not_a_publishing_payload(hook):
    # Arrange
    content = '[{"body": "x"}]'

    # Act
    looks = hook.looks_like_publishing_json(content)

    # Assert
    assert looks is False


def test_text_blocks_come_from_every_prose_field(hook):
    # Arrange
    content = json.dumps(
        {
            "body": "b",
            "title": "t",
            "message": "m",
            "comments": ["skip", {"body": ""}, {"body": "c"}],
        }
    )

    # Act
    blocks = hook.extract_publishing_text_blocks(content)

    # Assert
    assert blocks == [
        ("body", "b"),
        ("title", "t"),
        ("message", "m"),
        ("comments[2].body", "c"),
    ]


@pytest.mark.parametrize("content", ["{bad", "[1, 2]"])
def test_text_blocks_of_a_non_object_are_empty(hook, content):
    # Arrange
    content_input = content

    # Act
    blocks = hook.extract_publishing_text_blocks(content_input)

    # Assert
    assert blocks == []


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("gh api x --input 'unterminated", []),
        ("gh api x --input=/a.json --input=", ["/a.json"]),
        ("gh api x --input @/a.json", ["/a.json"]),
        ("gh api x -F body=@/b.md", ["/b.md"]),
        ("gh pr create --body-file /c.md --body-file /c.md", ["/c.md"]),
    ],
)
def test_referenced_payload_files(hook, command, expected):
    # Arrange
    command_input = command

    # Act
    paths = hook.extract_referenced_files(command_input)

    # Assert
    assert paths == expected


def _absent_file(directory: Path) -> Path:
    return directory / "absent.json"


def _oversized_file(directory: Path) -> Path:
    large = directory / "large.json"
    large.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    return large


def _unreadable_file(directory: Path) -> Path:
    locked = directory / "locked.json"
    locked.write_text("{}", encoding="utf-8")
    locked.chmod(0)
    return locked


def _directory(directory: Path) -> Path:
    return directory


@pytest.mark.parametrize(
    "make_path",
    [
        _absent_file,
        _oversized_file,
        pytest.param(
            _unreadable_file,
            marks=pytest.mark.skipif(
                os.geteuid() == 0, reason="root reads files without permission bits"
            ),
        ),
        _directory,
    ],
)
def test_payload_files_that_cannot_be_read_yield_nothing(hook, tmp_path, make_path):
    # Arrange
    path = make_path(tmp_path)

    # Act
    content = hook.read_payload_file(str(path))

    # Assert
    assert content is None


def test_a_leak_in_a_json_payload_file_blocks(tmp_path, tool_use, run_hook):
    # Arrange
    payload_file = tmp_path / "reply.json"
    payload_file.write_text(json.dumps({"body": LEAK}), encoding="utf-8")
    command = f"gh api repos/o/r/issues/1/comments --input {payload_file}"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, f"body (bash-payload:{payload_file})")


def test_a_leak_in_a_plain_payload_file_blocks(tmp_path, tool_use, run_hook):
    # Arrange
    payload_file = tmp_path / "body.md"
    payload_file.write_text(LEAK, encoding="utf-8")
    payload = tool_use("Bash", {"command": f"gh pr create --body-file {payload_file}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, f"{payload_file} (bash-payload)")


@pytest.mark.parametrize(
    ("tool", "tool_input", "field"),
    [
        (
            "Write",
            {"file_path": PAYLOAD_JSON, "content": json.dumps({"body": LEAK})},
            "body",
        ),
        (
            "Write",
            {
                "file_path": PAYLOAD_JSON,
                "content": json.dumps({"comments": [], "commit_id": LEAK}),
            },
            "content",
        ),
        ("Edit", {"file_path": PAYLOAD_JSON, "new_string": LEAK}, "new_string"),
        ("Edit", {"file_path": DOC, "new_string": LEAK}, "new_string"),
        (
            "MultiEdit",
            {
                "file_path": DOC,
                "edits": [
                    {"new_string": "one"},
                    {"new_string": "two"},
                    {"new_string": LEAK},
                ],
            },
            "edits[2].new_string",
        ),
        (
            "MultiEdit",
            {"file_path": PAYLOAD_JSON, "edits": [{"new_string": LEAK}]},
            "edits[0].new_string",
        ),
    ],
)
def test_a_leak_written_to_a_published_file_blocks(
    tool, tool_input, field, tool_use, run_hook
):
    # Arrange
    payload = tool_use(tool, tool_input)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, f"{field} ({tool_input['file_path']})")


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Write", {"file_path": PAYLOAD_JSON, "content": json.dumps({"x": LEAK})}),
        ("Write", {"file_path": "/tmp/project/app.py", "content": LEAK}),
        ("Edit", {"file_path": DOC, "new_string": None}),
        ("Read", {"file_path": DOC}),
    ],
)
def test_text_it_does_not_read_is_allowed(tool, tool_input, tool_use, run_hook):
    # Arrange
    payload = tool_use(tool, tool_input)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "P1: fix the loop",
            "internal severity tier (P0/P1/P2 scaffolding): ...P1: fix the loop...",
        ),
        (
            "## " + "Blast Radius Summary",
            "internal section heading: ...## " + "Blast Radius Summary...",
        ),
        (
            "--" + "backend review of this PR",
            "skill invocation flag in review preamble: ...--"
            + "backend review of this PR...",
        ),
    ],
)
def test_scaffolding_in_markdown_is_found(hook, text, expected):
    # Arrange
    content_kind = "markdown"

    # Act
    hits = hook.find_leaks(text, content_kind)

    # Assert
    assert hits == [expected]


def test_a_skill_flag_without_review_language_is_not_scaffolding(hook):
    # Arrange
    text = "--" + "backend service owns the queue"

    # Act
    hits = hook.find_leaks(text, "markdown")

    # Assert
    assert hits == []


@pytest.mark.parametrize(
    "env", [{"CONFIG_LEAKAGE_DISABLE": "1"}, {"CLAUDE_DISABLED_HOOKS": HOOK}]
)
def test_an_explicit_switch_allows(env, tool_use, run_hook):
    # Arrange
    payload = tool_use("Edit", {"file_path": DOC, "new_string": LEAK})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_live_bypass_entry_allows(tmp_path, tool_use, run_hook):
    # Arrange
    state = tmp_path / "bypass.json"
    set_bypass(HOOK, ttl_seconds=120, state_path=state)
    payload = tool_use("Edit", {"file_path": DOC, "new_string": LEAK})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert_allowed(result)


def test_a_payload_that_is_not_json_blocks():
    # Arrange
    env = apply_coverage_env(dict(os.environ))
    env["CLAUDE_BYPASS_STATE"] = os.devnull

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert (proc.returncode, "could not read its input" in proc.stderr) == (2, True)


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Write", {"file_path": DOC, "content": 3}),
        ("MultiEdit", {"file_path": DOC, "edits": ["x", {"new_string": 1}]}),
    ],
)
def test_a_text_field_that_is_not_a_string_blocks(tool, tool_input, tool_use, run_hook):
    # Arrange
    payload = tool_use(tool, tool_input)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "could not read its input")

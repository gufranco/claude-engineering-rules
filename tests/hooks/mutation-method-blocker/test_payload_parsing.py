"""Payload-parsing coverage.

Item 128 of the plan. Validates the three accepted payload shapes
(Write, Edit, MultiEdit) plus the failure-mode contract:

  - Missing tool_name or tool_input: exit 0 (no payload, nothing to scan).
  - Malformed JSON over stdin: exit 0 (best-effort, never crash).
  - Empty content: exit 0 (no text to inspect).
  - Unsupported tool: exit 0 (out of scope).
"""

from __future__ import annotations


from conftest import HOOK_PATH


def test_write_payload_parsed(run_hook):
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "items.push(value)"},
    }

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr


def test_edit_payload_parsed(run_hook):
    # Arrange
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/repo/src/app.ts",
            "new_string": "items.push(value)",
        },
    }

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr


def test_multi_edit_payload_parsed(run_hook):
    # Arrange
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "/repo/src/app.ts",
            "edits": [
                {"new_string": "items.push(value)"},
                {"new_string": "list.sort()"},
            ],
        },
    }

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr
    assert "array.sort" in stderr


def test_unsupported_tool_returns_zero(run_hook):
    # Arrange
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_missing_tool_name_returns_zero(run_hook):
    # Arrange
    payload = {
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "items.push(x)"}
    }

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_missing_tool_input_returns_zero(run_hook):
    # Arrange
    payload = {"tool_name": "Edit"}

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_empty_content_returns_zero(run_hook):
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": ""},
    }

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_empty_edits_returns_zero(run_hook):
    # Arrange
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {"file_path": "/repo/src/app.ts", "edits": []},
    }

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_malformed_json_returns_zero():
    # Arrange / Act
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="this is not json",
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_HOOK_AUDIT_DISABLE": "1", "HOME": "/tmp"},
        timeout=6.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 0


def test_non_string_content_returns_zero(run_hook):
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": 12345},
    }

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_skipped_extension_returns_zero(run_hook):
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.py", "content": "items.push(value)"},
    }

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_skipped_test_path_returns_zero(run_hook):
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/app.test.ts",
            "content": "items.push(value)",
        },
    }

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_skipped_migration_path_returns_zero(run_hook):
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/migrations/0001-init.ts",
            "content": "items.push(value)",
        },
    }

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0


def test_multi_edit_non_dict_edit_skipped(run_hook):
    # Arrange
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "/repo/src/app.ts",
            "edits": [
                "string-not-dict",
                {"new_string": "items.push(value)"},
            ],
        },
    }

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr


def test_records_and_tuples_syntax_does_not_crash(run_hook):
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/app.ts",
            "content": (
                "const r = #{ x: 1, y: 2 };\n"
                "const t = #[1, 2, 3];\n"
                "const nested = #{ pair: #[1, 2], tag: 'r' };\n"
            ),
        },
    }

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, (
        f"hook must not crash on withdrawn Records/Tuples syntax; stderr: {stderr}"
    )


def test_records_and_tuples_with_mutation_still_blocked(run_hook):
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/app.ts",
            "content": (
                "const r = #{ x: 1 };\nconst items = [1, 2, 3];\nitems.push(4);\n"
            ),
        },
    }

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr

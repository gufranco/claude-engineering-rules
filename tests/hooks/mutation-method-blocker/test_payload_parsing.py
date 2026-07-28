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
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "items.push(value)"},
    }

    code, stderr = run_hook(payload)

    assert code == 2
    assert "array.push" in stderr


def test_edit_payload_parsed(run_hook):
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/repo/src/app.ts",
            "new_string": "items.push(value)",
        },
    }

    code, stderr = run_hook(payload)

    assert code == 2
    assert "array.push" in stderr


def test_multi_edit_payload_parsed(run_hook):
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

    code, stderr = run_hook(payload)

    assert code == 2
    assert "array.push" in stderr
    assert "array.sort" in stderr


def test_unsupported_tool_returns_zero(run_hook):
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}

    code, _ = run_hook(payload)

    assert code == 0


def test_missing_tool_name_returns_zero(run_hook):
    payload = {
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "items.push(x)"}
    }

    code, _ = run_hook(payload)

    assert code == 0


def test_missing_tool_input_returns_zero(run_hook):
    payload = {"tool_name": "Edit"}

    code, _ = run_hook(payload)

    assert code == 0


def test_empty_content_returns_zero(run_hook):
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": ""},
    }

    code, _ = run_hook(payload)

    assert code == 0


def test_empty_edits_returns_zero(run_hook):
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {"file_path": "/repo/src/app.ts", "edits": []},
    }

    code, _ = run_hook(payload)

    assert code == 0


def test_malformed_json_returns_zero():
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

    assert proc.returncode == 0


def test_non_string_content_returns_zero(run_hook):
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": 12345},
    }

    code, _ = run_hook(payload)

    assert code == 0


def test_skipped_extension_returns_zero(run_hook):
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.py", "content": "items.push(value)"},
    }

    code, _ = run_hook(payload)

    assert code == 0


def test_skipped_test_path_returns_zero(run_hook):
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/app.test.ts",
            "content": "items.push(value)",
        },
    }

    code, _ = run_hook(payload)

    assert code == 0


def test_skipped_migration_path_returns_zero(run_hook):
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/migrations/0001-init.ts",
            "content": "items.push(value)",
        },
    }

    code, _ = run_hook(payload)

    assert code == 0


def test_multi_edit_non_dict_edit_skipped(run_hook):
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

    code, stderr = run_hook(payload)

    assert code == 2
    assert "array.push" in stderr


def test_records_and_tuples_syntax_does_not_crash(run_hook):
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

    code, stderr = run_hook(payload)

    assert code == 0, (
        f"hook must not crash on withdrawn Records/Tuples syntax; stderr: {stderr}"
    )


def test_records_and_tuples_with_mutation_still_blocked(run_hook):
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/app.ts",
            "content": (
                "const r = #{ x: 1 };\nconst items = [1, 2, 3];\nitems.push(4);\n"
            ),
        },
    }

    code, stderr = run_hook(payload)

    assert code == 2
    assert "array.push" in stderr

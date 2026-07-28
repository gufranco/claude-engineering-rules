"""Tests for `scripts/hook_io.py`."""

from __future__ import annotations
import io
import json
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from _lib.hook_io import (  # noqa: E402
    ToolUse,
    add_post_context,
    allow,
    ask,
    block,
    defer,
    modify_input,
    read_input,
)


def test_read_input_parses_full_payload(monkeypatch):
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/repo/a.ts", "new_string": "x"},
        "cwd": "/repo",
        "session_id": "abc",
        "transcript_path": "/tmp/t.jsonl",
        "hook_event_name": "PreToolUse",
        "permission_mode": "auto",
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    use = read_input()
    assert use.tool_name == "Edit"
    assert use.tool_input == {"file_path": "/repo/a.ts", "new_string": "x"}
    assert use.cwd == "/repo"
    assert use.session_id == "abc"
    assert use.hook_event_name == "PreToolUse"
    assert use.extra == {"permission_mode": "auto"}


def test_read_input_handles_invalid_json(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    use = read_input()
    assert use == ToolUse()


def test_read_input_handles_empty_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    use = read_input()
    assert use == ToolUse()


def test_read_input_rejects_non_dict_tool_input(monkeypatch):
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": "weird"})),
    )
    use = read_input()
    assert use.tool_input == {}


def test_read_input_rejects_top_level_list(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps([1, 2, 3])))
    use = read_input()
    assert use == ToolUse()


def test_block_prints_reason_and_returns_2(capsys):
    code = block("blocked because reason", suggestion="run X instead")
    captured = capsys.readouterr()
    assert code == 2
    assert "blocked because reason" in captured.err
    assert "run X instead" in captured.err


def test_block_without_suggestion(capsys):
    code = block("nope")
    captured = capsys.readouterr()
    assert code == 2
    assert "nope" in captured.err
    assert "Fix:" not in captured.err


def test_block_with_empty_reason(capsys):
    code = block("")
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err == ""


def test_block_records_audit_payload(monkeypatch, tmp_path):
    captured: list[dict[str, object]] = []

    def fake_record(**fields):
        captured.append(fields)

    fake_module = type(sys)("_lib.audit_log")
    fake_module.record = fake_record  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_lib.audit_log", fake_module)
    code = block(
        "blocked",
        audit_payload={"hook": "x", "decision": "block", "reason": "y"},
    )
    assert code == 2
    assert captured == [{"hook": "x", "decision": "block", "reason": "y"}]


def test_allow_returns_zero():
    assert allow() == 0


def test_defer_returns_zero():
    assert defer() == 0


def test_ask_returns_one_with_message(capsys):
    code = ask("please clarify")
    captured = capsys.readouterr()
    assert code == 1
    assert "please clarify" in captured.err


def test_ask_with_empty_message(capsys):
    code = ask("")
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == ""


def test_modify_input_emits_v2_envelope(capsys):
    original = ToolUse(
        tool_name="Edit",
        tool_input={"file_path": "/repo/a.ts", "new_string": "x"},
        hook_event_name="PreToolUse",
    )
    code = modify_input({"new_string": "y"}, original=original)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert code == 0
    spec = parsed["hookSpecificOutput"]
    assert spec["hookEventName"] == "PreToolUse"
    assert spec["permissionDecision"] == "allow"
    assert spec["modifiedInput"] == {"file_path": "/repo/a.ts", "new_string": "y"}


def test_modify_input_falls_back_to_allow_when_updates_empty():
    original = ToolUse(tool_name="Edit")
    assert modify_input({}, original=original) == 0


def test_add_post_context_emits_v2_envelope(capsys):
    code = add_post_context("here is some extra info")
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert code == 0
    spec = parsed["hookSpecificOutput"]
    assert spec["hookEventName"] == "PostToolUse"
    assert spec["additionalContext"] == "here is some extra info"


def test_add_post_context_no_text_falls_back_to_allow():
    assert add_post_context("") == 0


@pytest.mark.parametrize(
    "raw,expected_tool",
    [
        ("{}", ""),
        ('{"tool_name": null}', ""),
        ('{"tool_name": 123}', "123"),
    ],
)
def test_read_input_robust_to_partial_payload(monkeypatch, raw, expected_tool):
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    use = read_input()
    assert use.tool_name == expected_tool


def test_block_silent_when_audit_log_module_lacks_record(monkeypatch, capsys):
    fake_module = type(sys)("audit_log")
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)
    code = block("blocked", audit_payload={"hook": "x", "decision": "block"})
    captured = capsys.readouterr()
    assert code == 2
    assert "blocked" in captured.err


def test_block_swallows_oserror_from_record(monkeypatch, capsys):
    def boom(**_fields):
        raise OSError("disk full")

    fake_module = type(sys)("audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)
    code = block("blocked", audit_payload={"hook": "x", "decision": "block"})
    captured = capsys.readouterr()
    assert code == 2
    assert "blocked" in captured.err


def test_block_swallows_typeerror_from_record(monkeypatch):
    def boom(**_fields):
        raise TypeError("bad signature")

    fake_module = type(sys)("audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)
    assert block("blocked", audit_payload={"hook": "x"}) == 2


def test_block_swallows_valueerror_from_record(monkeypatch):
    def boom(**_fields):
        raise ValueError("invalid")

    fake_module = type(sys)("audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)
    assert block("blocked", audit_payload={"hook": "x"}) == 2


def test_modify_input_falls_back_to_allow_on_serialization_error(monkeypatch):
    original = ToolUse(
        tool_name="Edit",
        tool_input={"file_path": "/repo/a.ts"},
        hook_event_name="PreToolUse",
    )

    def fail_write(_data):
        raise OSError("broken pipe")

    monkeypatch.setattr(sys.stdout, "write", fail_write)
    code = modify_input({"new_string": "y"}, original=original)
    assert code == 0


def test_add_post_context_falls_back_to_allow_on_serialization_error(monkeypatch):
    def fail_write(_data):
        raise OSError("broken pipe")

    monkeypatch.setattr(sys.stdout, "write", fail_write)
    code = add_post_context("some text")
    assert code == 0

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "hooks"
HOOK_PATH = SCRIPTS_DIR / "mutation-method-blocker.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_detectors_core as core  # noqa: E402
from _lib import mutation_match_filter as match_filter  # noqa: E402
from _lib import suppression as supp  # noqa: E402


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "_mmb_hook_under_test", str(HOOK_PATH)
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load hook module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HOOK_MODULE = _load_hook_module()


def test_hook_exposes_no_allow_marker_api():
    # Arrange
    removed = (
        "_file_marker_active",
        "_line_allow_marker_active",
        "_is_line_only_marker",
        "ALLOW_FILE_MARKER",
        "ALLOW_LINE_MARKER",
    )

    # Act
    present = [name for name in removed if hasattr(HOOK_MODULE, name)]

    # Assert
    assert present == []


def test_hook_inside_state_mgmt_scope_empty_lines_state_filename():
    # Arrange
    lines: list[str] = []
    file_path = "/repo/src/userSlice.ts"

    # Act
    in_scope, label = match_filter.is_inside_state_mgmt_scope(lines, 0, file_path)

    # Assert
    assert in_scope is True
    assert label == "state-mgmt-filename"


def test_hook_inside_state_mgmt_scope_empty_lines_regular_path():
    # Arrange
    lines: list[str] = []
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = match_filter.is_inside_state_mgmt_scope(lines, 0, file_path)

    # Assert
    assert in_scope is False
    assert label is None


def test_hook_inside_state_mgmt_scope_blank_opener():
    # Arrange
    lines = [
        "createSlice({",
        "",
        "  reducers: {",
        "    inc(state) { state.count += 1; }",
        "  }",
        "})",
    ]
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = match_filter.is_inside_state_mgmt_scope(lines, 3, file_path)

    # Assert
    assert in_scope is True
    assert label == "redux-toolkit"


def test_hook_inside_state_mgmt_scope_yjs_receiver_match():
    # Arrange
    lines = [
        "const yArr = new Y.Array();",
        "yArr.push([1]);",
    ]
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = match_filter.is_inside_state_mgmt_scope(lines, 1, file_path)

    # Assert
    assert in_scope is True
    assert label == "yjs-crdt"


def test_hook_main_invalid_json_payload_blocks(monkeypatch):
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO("not-json"))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        HOOK_MODULE.main()

    # Assert
    assert exit_info.value.code == 2


def test_hook_main_disable_env(monkeypatch):
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_DISABLE", "1")
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO('{"tool_name": "Write"}'))

    # Act
    result = HOOK_MODULE.main()

    # Assert
    assert result == 0


def test_hook_main_no_findings_perf_budget_exceeded(monkeypatch, capsys):
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "const x = 1;"},
    }
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO(json.dumps(payload)))
    counter = iter([0.0, 1.0])
    monkeypatch.setattr(HOOK_MODULE.time, "perf_counter", lambda: next(counter))

    # Act
    result = HOOK_MODULE.main()

    # Assert
    assert result == 0


def test_hook_main_block_perf_budget_exceeded(monkeypatch, capsys):
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "items.push(x);"},
    }
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO(json.dumps(payload)))
    counter = iter([0.0, 1.0])
    monkeypatch.setattr(HOOK_MODULE.time, "perf_counter", lambda: next(counter))

    # Act
    result = HOOK_MODULE.main()

    # Assert
    assert result == 2
    captured = capsys.readouterr()
    assert "array.push" in captured.err


def test_hook_normalize_payload_unsupported_tool():
    # Arrange
    tool = "Bash"
    tool_input = {"command": "ls"}

    # Act
    result = HOOK_MODULE._normalize_payload(tool, tool_input)

    # Assert
    assert result == []


def test_hook_normalize_payload_multi_edit_with_dict_edits():
    # Arrange
    tool = "MultiEdit"
    tool_input = {
        "file_path": "/repo/src/app.ts",
        "edits": [
            {"new_string": "items.push(x);"},
            "not-a-dict",
            {"new_string": 123},
        ],
    }

    # Act
    result = HOOK_MODULE._normalize_payload(tool, tool_input)

    # Assert
    assert len(result) == 1
    assert result[0][0] == "/repo/src/app.ts"
    assert result[0][2] == "items.push(x);"


def test_hook_format_findings_truncates_after_max():
    # Arrange
    matches = [
        core.Match(
            line=i, col=1, text=f"line{i}", detector="array.push", fix_hint="hint"
        )
        for i in range(1, 12)
    ]

    # Act
    out = HOOK_MODULE._format_findings("/repo/src/app.ts", matches)

    # Assert
    assert len(out) == 18
    assert out[-1] == "      ... and 3 more"


def test_hook_build_message_contains_rule_reference():
    # Arrange
    findings = ["  - /repo/src/app.ts:", "      L1:1 [array.push] items.push(x);"]

    # Act
    msg = HOOK_MODULE._build_message(findings)

    # Assert
    assert "Immutability" in msg
    assert "array.push" in msg


def test_hook_filter_matches_file_allow_marker_does_not_suppress():
    # Arrange
    text = "// @allow-mutation -- justified\nitems.push(x);\n"
    matches = [core.Match(line=2, col=1, text="items.push(x);", detector="array.push")]
    block_state = supp.compute_block_state(text.splitlines())

    # Act
    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    # Assert
    assert len(survived) == 1
    assert reasons == {}


def test_hook_filter_matches_ts_nocheck_still_suppresses():
    # Arrange
    text = "// @ts-nocheck\nitems.push(x);\n"
    matches = [core.Match(line=2, col=1, text="items.push(x);", detector="array.push")]
    block_state = supp.compute_block_state(text.splitlines())

    # Act
    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    # Assert
    assert survived == []
    assert reasons == {"ts-nocheck": 1}


def test_hook_filter_matches_param_allowlist_property_skipped():
    # Arrange
    text = "function reduce(acc, x) { acc.foo = x; }"
    matches = [
        core.Match(
            line=1,
            col=27,
            text=text,
            detector="property.assignment",
            metadata={"receiver": "acc", "prop": "foo"},
        )
    ]
    block_state = supp.compute_block_state(text.splitlines())

    # Act
    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    # Assert
    assert survived == []
    assert reasons.get("param-allowlist") == 1


def test_hook_filter_matches_framework_receiver_array_push_skipped():
    # Arrange
    text = "router.push('/home');\n"
    matches = [
        core.Match(
            line=1,
            col=1,
            text=text.strip(),
            detector="array.push",
            metadata={"owner": "router"},
        )
    ]
    block_state = supp.compute_block_state(text.splitlines())

    # Act
    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    # Assert
    assert survived == []
    assert reasons.get("framework-receiver") == 1


def test_hook_inside_state_mgmt_scope_same_line_immer_produce():
    # Arrange
    lines = ["const next = produce(state, (draft) => { draft.items.push(1); });"]

    # Act
    in_scope, label = match_filter.is_inside_state_mgmt_scope(
        lines, 0, "/repo/src/feature.ts"
    )

    # Assert
    assert in_scope is True
    assert label == "immer-produce"

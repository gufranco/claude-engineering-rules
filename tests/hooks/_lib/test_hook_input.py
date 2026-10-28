from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.hook_input import read_advisory_payload, read_hook_payload  # noqa: E402


def _stdin(monkeypatch: pytest.MonkeyPatch, raw: bytes) -> None:
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not json",
        b"\xff\xfe",
        b"[1, 2]",
        json.dumps({"tool_name": "Bash", "tool_input": "rm"}).encode(),
        json.dumps({"tool_name": "Bash", "tool_input": [1]}).encode(),
        json.dumps({"tool_name": "Bash", "tool_input": {"command": ["rm"]}}).encode(),
        json.dumps({"tool_name": "Write", "tool_input": {"content": 7}}).encode(),
        json.dumps({"tool_name": "MultiEdit", "tool_input": {"edits": "x"}}).encode(),
        json.dumps({"tool_name": "MultiEdit", "tool_input": {"edits": ["x"]}}).encode(),
        json.dumps(
            {"tool_name": "MultiEdit", "tool_input": {"edits": [{"new_string": 3}]}}
        ).encode(),
    ],
)
def test_an_unreadable_payload_blocks(monkeypatch, capsys, raw):
    # Arrange
    _stdin(monkeypatch, raw)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        read_hook_payload("demo-guard")

    # Assert
    assert (
        exit_info.value.code,
        "demo-guard could not read" in capsys.readouterr().err,
    ) == (2, True)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"tool_name": "Bash", "tool_input": {"command": "ls"}}, {"command": "ls"}),
        ({"tool_name": "Bash", "input": {"command": "ls"}}, {"command": "ls"}),
        ({"tool_name": "Bash", "tool_input": None}, {}),
        ({"tool_name": "Bash"}, {}),
    ],
)
def test_a_readable_payload_carries_an_object_tool_input(
    monkeypatch, payload, expected
):
    # Arrange
    _stdin(monkeypatch, json.dumps(payload).encode())

    # Act
    result = read_hook_payload("demo-guard")

    # Assert
    assert (result["tool_input"], result["tool_name"]) == (expected, "Bash")


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"\xff\xfe", "advisory: unreadable payload: "),
        (b"not json", "advisory: unreadable payload: "),
        (b"[1, 2]", "advisory: payload is not a JSON object"),
    ],
)
def test_read_advisory_payload_reads_bad_input_as_empty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    raw: bytes,
    message: str,
) -> None:
    # Arrange
    _stdin(monkeypatch, raw)

    # Act
    result = read_advisory_payload("advisory")

    # Assert
    assert result == {}
    assert capsys.readouterr().err.startswith(message)


def test_read_advisory_payload_returns_an_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _stdin(monkeypatch, json.dumps({"tool_name": "Read"}).encode())

    # Act
    result = read_advisory_payload("advisory")

    # Assert
    assert result == {"tool_name": "Read"}

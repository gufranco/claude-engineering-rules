from __future__ import annotations

import json
from typing import NamedTuple

BLOCK_EXIT_CODE = 2
ALLOW_EXIT_CODE = 0


class HookResult(NamedTuple):
    code: int
    stdout: str
    stderr: str


def assert_blocked(result: HookResult, reason_substring: str = "") -> tuple[int, str]:
    assert result.code == BLOCK_EXIT_CODE, (
        f"expected hook to block (exit 2) but got exit {result.code}.\nstderr:\n{result.stderr}"
    )
    if reason_substring:
        assert reason_substring in result.stderr, (
            f"expected stderr to contain {reason_substring!r}.\nstderr:\n{result.stderr}"
        )
    return result.code, result.stderr


def assert_allowed(result: HookResult) -> tuple[int, str]:
    assert result.code == ALLOW_EXIT_CODE, (
        f"expected hook to allow (exit 0) but got exit {result.code}.\nstderr:\n{result.stderr}"
    )
    return result.code, result.stderr


def assert_modified(
    result: HookResult, expected_diff: dict[str, object]
) -> dict[str, object]:
    assert result.code == ALLOW_EXIT_CODE, (
        f"expected hook to allow with modified input (exit 0) "
        f"but got exit {result.code}.\nstderr:\n{result.stderr}"
    )
    assert result.stdout.strip(), (
        "expected hook to print a v2 envelope on stdout but stdout was empty"
    )
    parsed: object = json.loads(result.stdout)
    assert isinstance(parsed, dict), (
        f"expected a JSON object on stdout, got {type(parsed).__name__}"
    )
    spec: object = parsed.get("hookSpecificOutput") or {}
    assert isinstance(spec, dict), (
        f"expected hookSpecificOutput to be a dict, got {type(spec).__name__}"
    )
    assert spec.get("permissionDecision") == "allow", (
        f"expected permissionDecision=allow, got {spec.get('permissionDecision')!r}"
    )
    modified = spec.get("modifiedInput")
    assert isinstance(modified, dict), (
        f"expected modifiedInput to be a dict, got {type(modified).__name__}"
    )
    for key, value in expected_diff.items():
        assert key in modified, f"expected modifiedInput to include key {key!r}"
        assert modified[key] == value, (
            f"expected modifiedInput[{key!r}] == {value!r}, got {modified[key]!r}"
        )
    return parsed

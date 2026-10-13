from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "mutation-method-blocker.py"
CASES_DIR = Path(__file__).parent / "cases"

HOOK_TIMEOUT_S = 6.0
DEFAULT_CASE_FILE = "/repo/src/business/conformance.ts"
VERDICT_TO_EXIT_CODE = {
    "allow": 0,
    "block": 2,
}


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing opening --- frontmatter")
    meta: dict[str, str] = {}
    body_start = -1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = i + 1
            break
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    if body_start < 0:
        raise ValueError("missing closing --- frontmatter")
    body = "\n".join(lines[body_start:])
    return meta, body


def _discover_cases() -> list[Path]:
    cases = sorted(CASES_DIR.rglob("*.test.ts")) if CASES_DIR.is_dir() else []
    if not cases:
        raise RuntimeError(f"no conformance cases found under {CASES_DIR}")
    return cases


def _build_payload(meta: dict[str, str], body: str) -> dict[str, object]:
    file_path = meta.get("file", DEFAULT_CASE_FILE)
    payload_kind = meta.get("payload", "write")
    if payload_kind == "edit":
        return {
            "tool_name": "Edit",
            "tool_input": {"file_path": file_path, "new_string": body},
        }
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": body},
    }


def _expectation(meta: dict[str, str], case_path: Path) -> tuple[int, str]:
    verdict = meta.get("verdict", "").strip()
    if verdict not in VERDICT_TO_EXIT_CODE:
        raise ValueError(f"unknown verdict {verdict!r} in {case_path}")
    detector = meta.get("detector", "").strip()
    return VERDICT_TO_EXIT_CODE[verdict], detector if verdict == "block" else ""


def _run_hook(payload: dict[str, object]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=HOOK_TIMEOUT_S,
        check=False,
    )
    return proc.returncode, proc.stderr


@pytest.mark.parametrize("case_path", _discover_cases(), ids=lambda p: p.stem)
def test_conformance_case(case_path: Path) -> None:
    # Arrange
    meta, body = _parse_frontmatter(case_path.read_text(encoding="utf-8"))
    expected_code, expected_detector = _expectation(meta, case_path)
    payload = _build_payload(meta, body)

    # Act
    code, stderr = _run_hook(payload)

    # Assert
    assert code == expected_code, (
        f"{case_path.name}: expected exit {expected_code}, got {code}\n"
        f"description: {meta.get('description', '')}\n"
        f"stderr:\n{stderr}"
    )
    assert expected_detector in stderr, (
        f"{case_path.name}: expected detector {expected_detector} in stderr, got:\n{stderr}"
    )

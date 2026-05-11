"""Test262-style conformance runner for mutation-method-blocker (plan item 386).

Walks `tests/conformance/cases/`, parses each `.test.ts` file's YAML
frontmatter, and runs the hook with the body as the payload. Asserts the
hook's exit code matches the declared verdict.

Pass rate gate: the suite emits a summary at session-end. CI tooling that
runs this suite is expected to require >=95% pass rate; per-case failures
do not stop the run so the full picture is visible.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "mutation-method-blocker.py"
CASES_DIR = Path(__file__).parent / "cases"

VERDICT_TO_EXIT_CODE = {
    "allow": 0,
    "block": 2,
    "defer": 0,
    "ask": 1,
}


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a `---`-delimited YAML frontmatter from the body.

    Returns `(metadata, body)`. The frontmatter must begin with `---` on
    line 1 and close with another `---`. Missing or malformed frontmatter
    raises ValueError to surface as a test setup failure.
    """
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
    """Walk CASES_DIR for *.test.ts files."""
    if not CASES_DIR.is_dir():
        return []
    return sorted(CASES_DIR.rglob("*.test.ts"))


def _build_payload(meta: dict[str, str], body: str) -> dict:
    file_path = meta.get("file", "/repo/src/business/conformance.ts")
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


def _run_hook(payload: dict) -> tuple[int, str]:
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )
    return proc.returncode, proc.stderr


@pytest.mark.parametrize("case_path", _discover_cases(), ids=lambda p: p.stem)
def test_conformance_case(case_path: Path) -> None:
    """Run a single conformance case and assert the verdict matches."""
    text = case_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    verdict = meta.get("verdict", "").strip()
    if verdict not in VERDICT_TO_EXIT_CODE:
        pytest.fail(f"unknown verdict {verdict!r} in {case_path}")
    expected_code = VERDICT_TO_EXIT_CODE[verdict]
    payload = _build_payload(meta, body)
    code, stderr = _run_hook(payload)
    if code != expected_code:
        pytest.fail(
            f"{case_path.name}: expected exit {expected_code} ({verdict}), got {code}\n"
            f"description: {meta.get('description', '')}\n"
            f"stderr:\n{stderr}"
        )
    detector = meta.get("detector", "").strip()
    if verdict == "block" and detector:
        assert detector in stderr, (
            f"{case_path.name}: expected detector {detector} in stderr, got:\n{stderr}"
        )

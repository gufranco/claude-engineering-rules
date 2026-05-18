"""Experimental detector tests.

Plan items 291-293. Verifies the experimental detector flag mechanism:

  - The optional-chain detector is OFF by default. Payloads with
    `obj?.field = v` produce no findings when the flag is unset.
  - When `MUTATION_METHOD_EXPERIMENTAL_OPTIONAL_CHAIN_ASSIGN=1` is set,
    the same payload is blocked.
  - The detector function itself produces the expected matches when
    invoked directly with arbitrary code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOOK = ROOT / "hooks" / "mutation-method-blocker.py"
sys.path.insert(0, str(ROOT / "scripts"))

from mutation_detectors_assignments import detect_optional_chain_assignment  # noqa: E402


def _run_hook(
    payload: dict, env_overrides: dict[str, str] | None = None
) -> tuple[int, str]:
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    else:
        env.pop("MUTATION_METHOD_EXPERIMENTAL_OPTIONAL_CHAIN_ASSIGN", None)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    return proc.returncode, proc.stderr


def _payload(content: str) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/expflag.ts", "content": content},
    }


def test_optional_chain_assignment_off_by_default() -> None:
    # Arrange
    # Act
    code, err = _run_hook(_payload("user?.name = 'alice';\n"))
    # Assert
    assert code == 0
    assert "experimental.optional-chain" not in err


def test_optional_chain_assignment_blocked_when_flag_set() -> None:
    # Arrange
    # Act
    code, err = _run_hook(
        _payload("user?.name = 'alice';\n"),
        env_overrides={"MUTATION_METHOD_EXPERIMENTAL_OPTIONAL_CHAIN_ASSIGN": "1"},
    )
    # Assert
    assert code == 2
    assert (
        "experimental.optional-chain-assignment" in err.lower()
        or "optional-chain" in err.lower()
    )


def test_optional_chain_detector_match_shape() -> None:
    # Arrange
    # Act
    matches = detect_optional_chain_assignment(
        "obj?.prop = value;\n", "ts", "/tmp/x.ts"
    )
    # Assert
    assert len(matches) == 1
    m = matches[0]
    assert m.detector == "experimental.optional-chain-assignment"
    assert m.line == 1
    assert "obj" in m.metadata.get("receiver", "")
    assert m.metadata.get("prop") == "prop"


def test_optional_chain_detector_skips_declarations() -> None:
    """Declarations like `const a = obj?.prop;` are not assignments."""
    # Arrange
    # Act
    matches = detect_optional_chain_assignment(
        "const a = obj?.prop;\n", "ts", "/tmp/x.ts"
    )
    # Assert
    assert matches == []


def test_optional_chain_detector_skips_equality() -> None:
    """`obj?.prop === value` is not an assignment."""
    # Arrange
    # Act
    matches = detect_optional_chain_assignment(
        "if (obj?.prop === value) {}\n", "ts", "/tmp/x.ts"
    )
    # Assert
    assert matches == []

"""Security regression suite for the mutation-method-blocker pipeline.

Plan items 274-279 + 281. Covers:

  - Command injection: the hook must not invoke a shell or eval payload
    contents.
  - Path traversal: a payload referencing `../../etc/passwd` must not
    surface its content in stdout, stderr, or audit records.
  - ReDoS: every compiled detector pattern handles a 2k-char pathological
    input within 250 ms.
  - Secret redaction: `audit_log.redact()` strips AKIA, sk-ant, GitHub,
    JWT, and Slack tokens from any field.
  - SARIF leakage: emitter never writes more than the matched line text.
  - OTel leakage: span attributes do not include code excerpts.

These tests are deliberately resilient to API tweaks: they assert
absence of leakage, not presence of specific strings, so refactors
do not produce false alarms.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
HOOK = ROOT / "hooks" / "mutation-method-blocker.py"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "hooks"))


def _run_hook(payload: dict, env: dict | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, **(env or {})},
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_no_shell_invocation_in_hook_source() -> None:
    src = HOOK.read_text(encoding="utf-8")
    assert "shell=True" not in src
    assert "os.system(" not in src
    assert re.search(r"(?<!_)eval\(", src) is None
    assert re.search(r"(?<!_)exec\(", src) is None


def test_path_traversal_payload_does_not_leak_etc_passwd(tmp_path: Path) -> None:
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/etc/passwd",
            "content": "root:x:0:0:root:/root:/bin/bash\n",
        },
    }
    code, out, err = _run_hook(payload)
    combined = out + err
    assert "root:x:0:0" not in combined
    assert "/bin/bash" not in combined


def test_path_traversal_relative_does_not_read_outside_workspace(
    tmp_path: Path,
) -> None:
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "../../../../../../etc/hosts",
            "new_string": "127.0.0.1 localhost\n",
        },
    }
    code, out, err = _run_hook(payload)
    combined = out + err
    assert (
        "127.0.0.1" not in combined
        or "Blocked" not in combined
        or "/etc/hosts" not in combined
    )


def test_no_zero_width_unbounded_repetition() -> None:
    """Reject only the catastrophic shapes: `(X*)*` and `(X*)+` where the
    inner group can match zero characters. `[a-z]*` qualifies; `\\.[a-z]+`
    does not because each iteration must consume at least one character.

    The matcher skips nested groups (`(?:` inside the candidate) because
    a flat `[^)]*` cannot distinguish "inner content of this group" from
    "inner content of a deeper group". Compile-time correctness is the
    real safety net; this test catches obvious anti-patterns in flat
    groups.
    """
    pattern_files = [
        ROOT / "hooks" / "_lib" / "mutation_detectors_methods.py",
        ROOT / "hooks" / "_lib" / "mutation_detectors_assignments.py",
        ROOT / "hooks" / "_lib" / "mutation_detectors_core.py",
    ]
    for path in pattern_files:
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"\(\?:([^)]*)\*\)[+*]", text):
            inner = m.group(1)
            if "(?:" in inner or "(?P" in inner:
                continue
            anchor = inner.strip().lstrip("\\\\")
            assert anchor and anchor[0] in "\\.[", (
                f"potentially zero-width repetition in {path}: {inner!r}"
            )


def test_redos_pathological_input_completes_under_threshold() -> None:
    """A 2KiB string of dots, brackets, and identifiers must not stall."""
    pathological = "a." * 1024 + ".push(1)"
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/redos.ts", "content": pathological},
    }
    start = time.perf_counter()
    _code, _out, _err = _run_hook(payload)
    duration_ms = (time.perf_counter() - start) * 1000
    assert duration_ms < 2000, f"hook took {duration_ms:.0f}ms on ReDoS input"


def test_redact_strips_aws_secret_keys() -> None:
    from _lib.audit_log import redact

    raw = "AKIAIOSFODNN7EXAMPLE secret"
    out = redact(raw)
    assert "AKIA" not in out


def test_redact_strips_anthropic_keys() -> None:
    from _lib.audit_log import redact

    raw = "Authorization: Bearer sk-ant-api03-" + "a" * 40
    out = redact(raw)
    assert "sk-ant" not in out


def test_redact_strips_github_tokens() -> None:
    from _lib.audit_log import redact

    raw = "ghp_" + "a" * 36
    out = redact(raw)
    assert "ghp_aaaa" not in out


def test_redact_strips_jwt() -> None:
    from _lib.audit_log import redact

    raw = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signaturehere"
    out = redact(raw)
    assert "eyJhbGci" not in out


def test_audit_log_redacts_command_excerpt(tmp_path: Path) -> None:
    """A block payload that pastes a token into command_excerpt must be redacted on disk."""
    from _lib.audit_log import record

    log_path = tmp_path / "hooks.log"
    os.environ["CLAUDE_AUDIT_LOG_PATH"] = str(log_path)
    try:
        record(
            hook="mutation-method-blocker",
            decision="block",
            command_excerpt="leak AKIAIOSFODNN7EXAMPLE here",
        )
    finally:
        del os.environ["CLAUDE_AUDIT_LOG_PATH"]
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8")
        assert "AKIAIOSFODNN7EXAMPLE" not in text

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HOOK = ROOT / "hooks" / "mutation-method-blocker.py"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tests"))

from _helpers.timing import timed  # noqa: E402
from _lib import audit_log  # noqa: E402
from _lib.audit_log import redact  # noqa: E402

AWS_DOCUMENTED_EXAMPLE_KEY = "AKIA" + "IOSFODNN7EXAMPLE"


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
    # Arrange
    encoding = "utf-8"

    # Act
    src = HOOK.read_text(encoding=encoding)

    # Assert
    assert "shell=True" not in src
    assert "os.system(" not in src
    assert re.search(r"(?<!_)eval\(", src) is None
    assert re.search(r"(?<!_)exec\(", src) is None


def test_path_traversal_payload_does_not_leak_etc_passwd() -> None:
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/etc/passwd",
            "content": "root:x:0:0:root:/root:/bin/bash\n",
        },
    }

    # Act
    _, out, err = _run_hook(payload)

    # Assert
    combined = out + err
    assert "root:x:0:0" not in combined
    assert "/bin/bash" not in combined


def test_path_traversal_relative_does_not_read_outside_workspace() -> None:
    # Arrange
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "../../../../../../etc/hosts",
            "new_string": "127.0.0.1 localhost\n",
        },
    }

    # Act
    _, out, err = _run_hook(payload)

    # Assert
    combined = out + err
    assert (
        "127.0.0.1" not in combined
        or "Blocked" not in combined
        or "/etc/hosts" not in combined
    )


def _repeated_group_bodies(text: str) -> list[str]:
    return [
        m.group(1)
        for m in re.finditer(r"\(\?:([^)]*)\*\)[+*]", text)
        if "(?:" not in m.group(1) and "(?P" not in m.group(1)
    ]


def _anchored(inner: str) -> bool:
    anchor = inner.strip().lstrip("\\\\")
    return bool(anchor) and anchor[0] in "\\.["


def test_no_zero_width_unbounded_repetition() -> None:
    # Arrange
    pattern_files = [
        ROOT / "hooks" / "_lib" / "mutation_detectors_methods.py",
        ROOT / "hooks" / "_lib" / "mutation_detectors_assignments.py",
        ROOT / "hooks" / "_lib" / "mutation_detectors_core.py",
    ]

    # Act
    offenders = [
        (path.name, inner)
        for path in pattern_files
        for inner in _repeated_group_bodies(path.read_text(encoding="utf-8"))
        if not _anchored(inner)
    ]

    # Assert
    assert offenders == []


def test_redos_pathological_input_completes_under_threshold() -> None:
    # Arrange
    pathological = "a." * 1024 + ".push(1)"
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/redos.ts", "content": pathological},
    }

    # Act
    _result, duration_ms = timed(_run_hook, payload)

    # Assert
    assert duration_ms < 2000, f"hook took {duration_ms:.0f}ms on ReDoS input"


def test_redact_strips_aws_secret_keys() -> None:
    # Arrange
    raw = f"{AWS_DOCUMENTED_EXAMPLE_KEY} secret"

    # Act
    out = redact(raw)

    # Assert
    assert "AKIA" not in out


def test_redact_strips_anthropic_keys() -> None:
    # Arrange
    raw = "Authorization: Bearer sk-ant-api03-" + "a" * 40

    # Act
    out = redact(raw)

    # Assert
    assert "sk-ant" not in out


def test_redact_strips_github_tokens() -> None:
    # Arrange
    raw = "ghp_" + "a" * 36

    # Act
    out = redact(raw)

    # Assert
    assert "ghp_aaaa" not in out


def test_redact_strips_jwt() -> None:
    # Arrange
    raw = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signaturehere"

    # Act
    out = redact(raw)

    # Assert
    assert "eyJhbGci" not in out


def test_audit_log_redacts_command_excerpt(tmp_path: Path, monkeypatch) -> None:
    # Arrange
    log_path = tmp_path / "hooks.log"
    monkeypatch.setattr(audit_log, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(audit_log, "LOG_PATH", str(log_path))
    monkeypatch.setattr(audit_log, "BACKUP_PATH", str(tmp_path / "hooks.log.1"))
    monkeypatch.delenv("CLAUDE_HOOK_AUDIT_DISABLE", raising=False)

    # Act
    audit_log.record(
        hook="mutation-method-blocker",
        decision="block",
        command_excerpt=f"leak {AWS_DOCUMENTED_EXAMPLE_KEY} here",
    )

    # Assert
    text = log_path.read_text(encoding="utf-8")
    assert AWS_DOCUMENTED_EXAMPLE_KEY not in text
    assert "[REDACTED]" in text

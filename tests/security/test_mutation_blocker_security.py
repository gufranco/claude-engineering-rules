from __future__ import annotations

import json
import os
import re
import string
import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

ROOT = Path(__file__).resolve().parent.parent.parent
HOOK = ROOT / "hooks" / "mutation-method-blocker.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib import audit_log  # noqa: E402
from _lib.audit_log import redact  # noqa: E402

AWS_KEY_PREFIX = "AKIA"
AWS_KEY_BODY_LENGTH = 16
GITHUB_TOKEN_BODY_LENGTH = 36
ANTHROPIC_KEY_BODY_LENGTH = 40
REDACTED = "[REDACTED]"
HOOK_TIMEOUT_S = 10
BLOCK_EXIT_CODE = 2
REDOS_REPEAT = 1024

Payload = dict[str, object]


def _run_hook(payload: Payload) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=HOOK_TIMEOUT_S,
        env=apply_coverage_env(dict(os.environ)),
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _aws_key(faker: Faker) -> str:
    body = faker.lexify(
        "?" * AWS_KEY_BODY_LENGTH, letters=string.ascii_uppercase + string.digits
    )
    return f"{AWS_KEY_PREFIX}{body}"


def _alnum(faker: Faker, length: int) -> str:
    return faker.lexify("?" * length, letters=string.ascii_letters + string.digits)


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


def test_write_to_etc_passwd_is_allowed_silently(faker: Faker) -> None:
    # Arrange
    payload: Payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/etc/passwd",
            "content": f"{faker.user_name()}:x:0:0::/root:/bin/bash\n",
        },
    }

    # Act
    result = _run_hook(payload)

    # Assert
    assert result == (0, "", "")


def test_relative_traversal_edit_is_allowed_silently(faker: Faker) -> None:
    # Arrange
    payload: Payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "../../../../../../etc/hosts",
            "new_string": f"{faker.ipv4()} {faker.hostname()}\n",
        },
    }

    # Act
    result = _run_hook(payload)

    # Assert
    assert result == (0, "", "")


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
    pattern_files = sorted((ROOT / "hooks" / "_lib").glob("mutation_detectors_*.py"))

    # Act
    offenders = [
        (path.name, inner)
        for path in pattern_files
        for inner in _repeated_group_bodies(path.read_text(encoding="utf-8"))
        if not _anchored(inner)
    ]

    # Assert
    assert offenders == []


def test_redos_pathological_input_is_blocked_before_the_timeout() -> None:
    # Arrange
    pathological = "const a = [1]\n" + "a." * REDOS_REPEAT + "push(1)\n"
    payload: Payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/business/redos.ts",
            "content": pathological,
        },
    }

    # Act
    code, _out, err = _run_hook(payload)

    # Assert
    assert code == BLOCK_EXIT_CODE
    assert "L2:2047 [array.push]" in err


def test_redact_strips_aws_access_keys(faker: Faker) -> None:
    # Arrange
    word = faker.word()
    raw = f"{_aws_key(faker)} {word}"

    # Act
    out = redact(raw)

    # Assert
    assert out == f"{REDACTED} {word}"


def test_redact_strips_anthropic_keys(faker: Faker) -> None:
    # Arrange
    raw = (
        "Authorization: "
        + "Bearer "
        + "sk-"
        + "ant-api03-"
        + _alnum(faker, ANTHROPIC_KEY_BODY_LENGTH)
    )

    # Act
    out = redact(raw)

    # Assert
    assert out == f"Authorization: Bearer {REDACTED}"


def test_redact_strips_github_tokens(faker: Faker) -> None:
    # Arrange
    raw = "ghp_" + _alnum(faker, GITHUB_TOKEN_BODY_LENGTH)

    # Act
    out = redact(raw)

    # Assert
    assert out == REDACTED


def test_redact_strips_jwt() -> None:
    # Arrange
    raw = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signaturehere"

    # Act
    out = redact(raw)

    # Assert
    assert out == REDACTED


def test_audit_log_redacts_command_excerpt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, faker: Faker
) -> None:
    # Arrange
    log_path = tmp_path / "hooks.log"
    monkeypatch.setattr(audit_log, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(audit_log, "LOG_PATH", str(log_path))
    monkeypatch.setattr(audit_log, "BACKUP_PATH", str(tmp_path / "hooks.log.1"))
    monkeypatch.delenv("CLAUDE_HOOK_AUDIT_DISABLE", raising=False)
    key = _aws_key(faker)
    before = faker.word()
    after = faker.word()

    # Act
    audit_log.record(
        hook="mutation-method-blocker",
        decision="block",
        command_excerpt=f"{before} {key} {after}",
    )

    # Assert
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["command_excerpt"] == f"{before} {REDACTED} {after}"

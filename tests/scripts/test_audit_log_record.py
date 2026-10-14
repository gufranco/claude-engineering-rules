from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from faker import Faker

from _helpers.audit_log_support import (
    AWS_STYLE_KEY,
    DETECTOR_TAG_LIMIT,
    EXCERPT_LIMIT,
    REDACTED,
    _read_records,
    audit_log,
)


SESSION_ENV_VARS = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "SESSION_ID")


class _StrOnly:
    def __init__(self, text: str) -> None:
        self.text = text

    def __str__(self) -> str:
        return self.text


def _clear_session_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SESSION_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _run_concurrent_writers(writers: int, per_writer: int) -> None:
    def worker(idx: int) -> None:
        for n in range(per_writer):
            audit_log.record(hook=f"w{idx}", decision="allow", reason=f"r-{idx}-{n}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def fail_rename(*_args: object, **_kwargs: object) -> None:
    raise OSError("simulated cross-device rename failure")


def boom(*_args: object, **_kwargs: object) -> None:
    raise OSError("readonly fs")


def test_record_redacts_command_excerpt(isolated_log: Path, faker: Faker) -> None:
    # Arrange
    command = faker.word()

    # Act
    audit_log.record(
        hook=faker.word(),
        decision="block",
        command_excerpt=f"{command} {AWS_STYLE_KEY}",
    )

    # Assert
    records = _read_records(isolated_log)
    assert [r["command_excerpt"] for r in records] == [f"{command} {REDACTED}"]


def test_record_truncates_command_excerpt(isolated_log: Path, faker: Faker) -> None:
    # Arrange
    long_cmd = "echo " + faker.pystr(min_chars=1000, max_chars=1000)

    # Act
    audit_log.record(hook=faker.word(), decision="allow", command_excerpt=long_cmd)

    # Assert
    records = _read_records(isolated_log)
    assert [r["command_excerpt"] for r in records] == [long_cmd[:EXCERPT_LIMIT]]


def test_rotation_triggers_when_log_exceeds_max_bytes(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path
) -> None:
    # Arrange
    monkeypatch.setattr(audit_log, "MAX_BYTES", 50)
    audit_log.record(hook="first", decision="allow")

    # Act
    audit_log.record(hook="second", decision="allow")

    # Assert
    backup_records = _read_records(Path(audit_log.BACKUP_PATH))
    current_records = _read_records(isolated_log)
    assert [r["hook"] for r in backup_records] == ["first"]
    assert [r["hook"] for r in current_records] == ["second"]


def test_rotation_replaces_existing_backup(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path
) -> None:
    # Arrange
    monkeypatch.setattr(audit_log, "MAX_BYTES", 50)
    Path(audit_log.LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(audit_log.BACKUP_PATH).write_text('{"hook":"stale"}\n', encoding="utf-8")
    audit_log.record(hook="primary", decision="allow")

    # Act
    audit_log.record(hook="next", decision="allow")

    # Assert
    backup_records = _read_records(Path(audit_log.BACKUP_PATH))
    assert [r.get("hook") for r in backup_records] == ["primary"]


def test_rotation_no_op_when_log_missing(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path
) -> None:
    # Arrange
    monkeypatch.setattr(audit_log, "MAX_BYTES", 50)

    # Act
    audit_log._rotate_if_needed()

    # Assert
    assert (isolated_log.exists(), Path(audit_log.BACKUP_PATH).exists()) == (
        False,
        False,
    )


def test_rotation_no_op_when_under_threshold(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    monkeypatch.setattr(audit_log, "MAX_BYTES", 10_000)
    audit_log.record(hook=faker.word(), decision="allow")
    content_before = isolated_log.read_text(encoding="utf-8")

    # Act
    audit_log._rotate_if_needed()

    # Assert
    assert isolated_log.read_text(encoding="utf-8") == content_before
    assert Path(audit_log.BACKUP_PATH).exists() is False


def test_rotation_swallows_oserror_on_rename(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    hook = faker.word()
    monkeypatch.setattr(audit_log, "MAX_BYTES", 10)
    audit_log.record(hook=hook, decision="allow")
    monkeypatch.setattr(audit_log.os, "rename", fail_rename)

    # Act
    audit_log._rotate_if_needed()

    # Assert
    assert [r["hook"] for r in _read_records(isolated_log)] == [hook]
    assert Path(audit_log.BACKUP_PATH).exists() is False


def test_concurrent_writers_produce_intact_lines(isolated_log: Path) -> None:
    # Arrange
    writers = 16
    per_writer = 25

    # Act
    _run_concurrent_writers(writers, per_writer)

    # Assert
    records = _read_records(isolated_log)
    assert sorted(str(r["reason"]) for r in records) == sorted(
        f"r-{idx}-{n}" for idx in range(writers) for n in range(per_writer)
    )


def test_record_with_no_fields_writes_timestamp_and_cwd_only(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path
) -> None:
    # Arrange
    _clear_session_env(monkeypatch)

    # Act
    audit_log.record()

    # Assert
    records = _read_records(isolated_log)
    assert [sorted(r) for r in records] == [["cwd", "ts"]]
    assert records[0]["cwd"] == os.getcwd()


def test_record_stringifies_a_non_serializable_field(
    isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    text = faker.word()

    # Act
    audit_log.record(hook=faker.word(), decision="allow", payload=_StrOnly(text))

    # Assert
    records = _read_records(isolated_log)
    assert [r["payload"] for r in records] == [text]


def test_record_skips_a_recursive_object(isolated_log: Path, faker: Faker) -> None:
    # Arrange
    cycle: dict[str, object] = {}
    cycle["self"] = cycle

    # Act
    audit_log.record(hook=faker.word(), decision="allow", payload=cycle)

    # Assert
    assert _read_records(isolated_log) == []


def test_record_silent_when_disable_env_set(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    monkeypatch.setenv("CLAUDE_HOOK_AUDIT_DISABLE", "1")

    # Act
    audit_log.record(hook=faker.word(), decision="allow")

    # Assert
    assert isolated_log.exists() is False


def test_record_swallows_makedirs_oserror(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    monkeypatch.setattr(audit_log.os, "makedirs", boom)

    # Act
    audit_log.record(hook=faker.word(), decision="allow")

    # Assert
    assert isolated_log.exists() is False


def test_record_with_long_detector_tag_writes_truncated(
    isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    long = faker.pystr(
        min_chars=DETECTOR_TAG_LIMIT * 4, max_chars=DETECTOR_TAG_LIMIT * 4
    )

    # Act
    audit_log.record(hook=faker.word(), decision="block", detector_tag=long)

    # Assert
    records = _read_records(isolated_log)
    assert [r["detector_tag"] for r in records] == [long[:DETECTOR_TAG_LIMIT]]


def test_record_normalizes_decision_class_on_write(
    isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    invalid = f"{faker.word()}-{faker.word()}"

    # Act
    audit_log.record(hook=faker.word(), decision_class=invalid)

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["decision_class"] == "warn"
    assert records[0]["original_decision_class"] == invalid


def test_record_clamps_confidence_score_on_write(
    isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    hook = faker.word()

    # Act
    audit_log.record(hook=hook, decision="allow", confidence_score=99)

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["confidence_score"] == 10


def test_record_autofills_cwd_when_missing(isolated_log: Path, faker: Faker) -> None:
    # Arrange
    hook = faker.word()

    # Act
    audit_log.record(hook=hook, decision="allow")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["cwd"] == os.getcwd()


def test_record_prefers_the_claude_code_session_id(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    primary = faker.uuid4()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", primary)
    monkeypatch.setenv("CLAUDE_SESSION_ID", faker.uuid4())

    # Act
    audit_log.record(hook=faker.word(), decision="allow")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == primary


def test_record_autofills_session_id_from_env(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    _clear_session_env(monkeypatch)
    session = faker.uuid4()
    monkeypatch.setenv("CLAUDE_SESSION_ID", session)

    # Act
    audit_log.record(hook=faker.word(), decision="allow")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == session


def test_record_falls_back_to_legacy_session_id_env(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    _clear_session_env(monkeypatch)
    session = faker.uuid4()
    monkeypatch.setenv("SESSION_ID", session)

    # Act
    audit_log.record(hook=faker.word(), decision="allow")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == session


def test_record_explicit_session_id_overrides_env(
    monkeypatch: pytest.MonkeyPatch, isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    explicit = faker.uuid4()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", faker.uuid4())

    # Act
    audit_log.record(hook=faker.word(), decision="allow", session_id=explicit)

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == explicit

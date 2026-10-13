from __future__ import annotations

import importlib
import json
import os
import sys
import threading
from pathlib import Path

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import audit_log  # noqa: E402

REDACTED = "[REDACTED]"
AWS_STYLE_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
EXCERPT_LIMIT = 240
DETECTOR_TAG_LIMIT = 80
DEFECT_PATTERN_TAG_LIMIT = 64
SESSION_ENV_VARS = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "SESSION_ID")

Record = dict[str, object]


class _StrOnly:
    def __init__(self, text: str) -> None:
        self.text = text

    def __str__(self) -> str:
        return self.text


@pytest.fixture
def isolated_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    log_dir = tmp_path / "logs"
    log_path = log_dir / "hooks.log"
    backup_path = log_dir / "hooks.log.1"
    monkeypatch.setattr(audit_log, "LOG_DIR", str(log_dir))
    monkeypatch.setattr(audit_log, "LOG_PATH", str(log_path))
    monkeypatch.setattr(audit_log, "BACKUP_PATH", str(backup_path))
    monkeypatch.delenv("CLAUDE_HOOK_AUDIT_DISABLE", raising=False)
    return log_path


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


def _read_records(log_path: Path) -> list[Record]:
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def fail_rename(*_args: object, **_kwargs: object) -> None:
    raise OSError("simulated cross-device rename failure")


def boom(*_args: object, **_kwargs: object) -> None:
    raise OSError("readonly fs")


def test_decision_class_passthrough_when_valid() -> None:
    # Arrange
    fields = {"decision_class": "block"}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out == {"decision_class": "block"}


@pytest.mark.parametrize(
    "valid_class",
    sorted(audit_log.ALLOWED_DECISION_CLASSES),
)
def test_each_allowed_decision_class_is_preserved(valid_class: str) -> None:
    # Arrange
    fields = {"decision_class": valid_class}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out == {"decision_class": valid_class}


def test_decision_class_invalid_string_is_demoted_to_warn(faker: Faker) -> None:
    # Arrange
    invalid = f"{faker.word()}-{faker.word()}"

    # Act
    out = audit_log._normalize_schema({"decision_class": invalid})

    # Assert
    assert out == {"decision_class": "warn", "original_decision_class": invalid}


def test_decision_class_non_string_is_demoted_to_warn(faker: Faker) -> None:
    # Arrange
    invalid = faker.pyint()

    # Act
    out = audit_log._normalize_schema({"decision_class": invalid})

    # Assert
    assert out == {"decision_class": "warn", "original_decision_class": invalid}


def test_confidence_score_clamps_high() -> None:
    # Arrange
    fields = {"confidence_score": 99}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["confidence_score"] == 10


def test_confidence_score_clamps_low() -> None:
    # Arrange
    fields = {"confidence_score": -3}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["confidence_score"] == 1


def test_confidence_score_inside_range_passes_through() -> None:
    # Arrange
    fields = {"confidence_score": 7}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["confidence_score"] == 7


def test_confidence_score_string_int_is_coerced() -> None:
    # Arrange
    fields = {"confidence_score": "5"}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["confidence_score"] == 5


def test_confidence_score_non_numeric_is_dropped(faker: Faker) -> None:
    # Arrange
    fields = {"confidence_score": faker.word()}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out == {}


def test_confidence_score_none_is_dropped() -> None:
    # Arrange
    fields = {"confidence_score": None}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out == {}


def test_detector_tag_truncates_to_max(faker: Faker) -> None:
    # Arrange
    long = faker.pystr(
        min_chars=DETECTOR_TAG_LIMIT + 50, max_chars=DETECTOR_TAG_LIMIT + 50
    )

    # Act
    out = audit_log._normalize_schema({"detector_tag": long})

    # Assert
    assert out == {"detector_tag": long[:DETECTOR_TAG_LIMIT]}


def test_detector_tag_non_string_is_dropped(faker: Faker) -> None:
    # Arrange
    fields = {"detector_tag": [faker.word()]}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out == {}


def test_defect_pattern_tag_truncates_to_max(faker: Faker) -> None:
    # Arrange
    long = faker.pystr(
        min_chars=DEFECT_PATTERN_TAG_LIMIT + 25, max_chars=DEFECT_PATTERN_TAG_LIMIT + 25
    )

    # Act
    out = audit_log._normalize_schema({"defect_pattern_tag": long})

    # Assert
    assert out == {"defect_pattern_tag": long[:DEFECT_PATTERN_TAG_LIMIT]}


def test_defect_pattern_tag_non_string_is_dropped(faker: Faker) -> None:
    # Arrange
    fields = {"defect_pattern_tag": faker.pyint()}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out == {}


def test_normalize_schema_preserves_unrelated_fields(faker: Faker) -> None:
    # Arrange
    fields = {"hook": faker.word(), "decision": "block", "reason": faker.sentence()}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out == fields


def test_defect_pattern_tags_constant_includes_canonical_set() -> None:
    # Arrange
    canonical = {
        "plausible-hallucination",
        "optimistic-error-handling",
        "shallow-validation",
        "copy-paste-drift",
        "missing-cleanup",
        "invented-api",
    }

    # Act
    missing = canonical - set(audit_log.DEFECT_PATTERN_TAGS)

    # Assert
    assert missing == set()


@pytest.mark.parametrize(
    "raw,expected",
    [
        (AWS_STYLE_KEY, REDACTED),
        ("sk-" + "ant-abc123def456ghi789jklmn", REDACTED),
        ("AIza" + "x" * 35, REDACTED),
        ("ghp_" + "a" * 36, REDACTED),
        ("github_pat_" + "a" * 22, REDACTED),
        ("glpat-" + "x" * 20, REDACTED),
        ("xo" + "xb-1234567890-abcdefghij", REDACTED),
        ("hf_" + "a" * 34, REDACTED),
        ("npm_" + "a" * 36, REDACTED),
        ("pypi-" + "a" * 16, REDACTED),
        ("ey" + "Jabcdefghij." + "ey" + "Jklmnopqrst.signaturefoo", REDACTED),
        ("-----BEGIN RSA " + "PRIVATE KEY-----", REDACTED),
        ("postgres" + "://user:secret@host:5432/db", f"{REDACTED}host:5432/db"),
        ("pass" + "word='supersecret'", REDACTED),
    ],
)
def test_redact_replaces_known_patterns(raw: str, expected: str) -> None:
    # Arrange
    secret_text = raw

    # Act
    out = audit_log.redact(secret_text)

    # Assert
    assert out == expected


@pytest.mark.parametrize(
    "secret",
    [
        "sk-proj-" + "A1b2C3d4" * 6,
        "sk-svcacct-" + "Z9y8X7w6" * 5,
        "sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc",
        "rk_test_" + "51H9xQ2LkzOjVb7nMp4Tq8Rs",
    ],
)
def test_redact_removes_current_key_shapes(secret: str) -> None:
    # Arrange
    line = f"key={secret} used"

    # Act
    out = audit_log.redact(line)

    # Assert
    assert out == f"key={REDACTED} used"


def test_redact_leaves_an_already_redacted_marker_unchanged(faker: Faker) -> None:
    # Arrange
    text = f"{faker.word()} {REDACTED} {faker.word()}"

    # Act
    out = audit_log.redact(text)

    # Assert
    assert out == text


def test_redact_empty_string_is_returned_as_is() -> None:
    # Arrange
    text = ""

    # Act
    out = audit_log.redact(text)

    # Assert
    assert out == ""


def test_redact_none_is_returned_as_is() -> None:
    # Arrange
    missing = None

    # Act
    out = audit_log.redact(missing)  # type: ignore[arg-type]

    # Assert
    assert out is None


def test_redact_leaves_non_secret_text_alone(faker: Faker) -> None:
    # Arrange
    text = faker.sentence()

    # Act
    out = audit_log.redact(text)

    # Assert
    assert out == text


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


def test_cli_writes_record_with_legacy_flags(isolated_log: Path, faker: Faker) -> None:
    # Arrange
    reason = faker.sentence()
    command = f"echo {faker.word()}"
    argv = [
        "--hook",
        "large-file-blocker",
        "--decision",
        "block",
        "--tool",
        "Bash",
        "--reason",
        reason,
        "--command",
        command,
    ]

    # Act
    code = audit_log._cli(argv)

    # Assert
    assert code == 0
    records = _read_records(isolated_log)
    assert len(records) == 1
    entry = records[0]
    assert entry["hook"] == "large-file-blocker"
    assert entry["decision"] == "block"
    assert entry["tool"] == "Bash"
    assert entry["reason"] == reason
    assert entry["command_excerpt"] == command


def test_cli_writes_record_with_new_schema_flags(
    isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    file_path = f"/repo/src/{faker.word()}.ts"
    latency = faker.pyint(min_value=1, max_value=999)
    argv = [
        "--hook",
        "mutation-method-blocker",
        "--decision",
        "block",
        "--decision-class",
        "block",
        "--detector-tag",
        "array.push",
        "--defect-pattern-tag",
        "missing-cleanup",
        "--confidence-score",
        "8",
        "--file-path",
        file_path,
        "--latency-ms",
        str(latency),
    ]

    # Act
    code = audit_log._cli(argv)

    # Assert
    assert code == 0
    records = _read_records(isolated_log)
    entry = records[0]
    assert entry["decision_class"] == "block"
    assert entry["detector_tag"] == "array.push"
    assert entry["defect_pattern_tag"] == "missing-cleanup"
    assert entry["confidence_score"] == 8
    assert entry["file_path"] == file_path
    assert entry["latency_ms"] == latency


def test_cli_rejects_unknown_decision_class(
    capsys: pytest.CaptureFixture[str], isolated_log: Path
) -> None:
    # Arrange
    argv = [
        "--hook",
        "x",
        "--decision",
        "block",
        "--decision-class",
        "nonsense",
    ]

    # Act
    with pytest.raises(SystemExit) as raised:
        audit_log._cli(argv)

    # Assert
    assert raised.value.code == 2
    assert "invalid choice: 'nonsense'" in capsys.readouterr().err
    assert _read_records(isolated_log) == []


def test_cli_rejects_invalid_decision(
    capsys: pytest.CaptureFixture[str], isolated_log: Path
) -> None:
    # Arrange
    argv = ["--hook", "x", "--decision", "wat"]

    # Act
    with pytest.raises(SystemExit) as raised:
        audit_log._cli(argv)

    # Assert
    assert raised.value.code == 2
    assert "invalid choice: 'wat'" in capsys.readouterr().err
    assert _read_records(isolated_log) == []


def test_cli_writes_a_minimal_allow_record(isolated_log: Path, faker: Faker) -> None:
    # Arrange
    hook = faker.word()
    argv = ["--hook", hook, "--decision", "allow"]

    # Act
    rc = audit_log._cli(argv)

    # Assert
    assert rc == 0
    records = _read_records(isolated_log)
    assert [(r["hook"], r["decision"]) for r in records] == [(hook, "allow")]


def test_module_can_be_imported_repeatedly() -> None:
    # Arrange
    module = audit_log

    # Act
    reloaded = importlib.reload(module)

    # Assert
    assert (
        reloaded.MAX_BYTES,
        reloaded.MAX_EXCERPT,
        reloaded.MAX_DETECTOR_TAG,
        reloaded.MAX_DEFECT_PATTERN_TAG,
    ) == (5 * 1024 * 1024, EXCERPT_LIMIT, DETECTOR_TAG_LIMIT, DEFECT_PATTERN_TAG_LIMIT)

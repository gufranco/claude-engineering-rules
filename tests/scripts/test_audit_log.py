from __future__ import annotations
import importlib
import json
import os
import sys
import threading
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from _lib import audit_log  # noqa: E402


@pytest.fixture
def isolated_log(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_path = log_dir / "hooks.log"
    backup_path = log_dir / "hooks.log.1"
    monkeypatch.setattr(audit_log, "LOG_DIR", str(log_dir))
    monkeypatch.setattr(audit_log, "LOG_PATH", str(log_path))
    monkeypatch.setattr(audit_log, "BACKUP_PATH", str(backup_path))
    monkeypatch.delenv("CLAUDE_HOOK_AUDIT_DISABLE", raising=False)
    return log_path


def _run_concurrent_writers(writers: int, per_writer: int) -> None:
    def worker(idx: int) -> None:
        for n in range(per_writer):
            audit_log.record(hook=f"w{idx}", decision="allow", reason=f"r-{idx}-{n}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def _read_records(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [
        json.loads(line) for line in log_path.read_text().splitlines() if line.strip()
    ]


def fail_rename(*_args, **_kwargs):
    raise OSError("simulated cross-device rename failure")


def boom(*_args, **_kwargs):
    raise OSError("readonly fs")


def test_decision_class_passthrough_when_valid():
    # Arrange
    fields = {"decision_class": "block"}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["decision_class"] == "block"
    assert "original_decision_class" not in out


@pytest.mark.parametrize(
    "valid_class",
    sorted(audit_log.ALLOWED_DECISION_CLASSES),
)
def test_each_allowed_decision_class_is_preserved(valid_class):
    # Arrange
    fields = {"decision_class": valid_class}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["decision_class"] == valid_class
    assert "original_decision_class" not in out


def test_decision_class_invalid_string_is_demoted_to_warn():
    # Arrange
    fields = {"decision_class": "wat"}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["decision_class"] == "warn"
    assert out["original_decision_class"] == "wat"


def test_decision_class_non_string_is_demoted_to_warn():
    # Arrange
    fields = {"decision_class": 42}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["decision_class"] == "warn"
    assert out["original_decision_class"] == 42


def test_confidence_score_clamps_high():
    # Arrange
    fields = {"confidence_score": 99}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["confidence_score"] == 10


def test_confidence_score_clamps_low():
    # Arrange
    fields = {"confidence_score": -3}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["confidence_score"] == 1


def test_confidence_score_inside_range_passes_through():
    # Arrange
    fields = {"confidence_score": 7}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["confidence_score"] == 7


def test_confidence_score_string_int_is_coerced():
    # Arrange
    fields = {"confidence_score": "5"}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out["confidence_score"] == 5


def test_confidence_score_non_numeric_is_dropped():
    # Arrange
    fields = {"confidence_score": "abc"}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert "confidence_score" not in out


def test_confidence_score_none_is_dropped():
    # Arrange
    fields = {"confidence_score": None}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert "confidence_score" not in out


def test_detector_tag_truncates_to_max():
    # Arrange
    long = "x" * (audit_log.MAX_DETECTOR_TAG + 50)

    # Act
    out = audit_log._normalize_schema({"detector_tag": long})

    # Assert
    assert len(out["detector_tag"]) == audit_log.MAX_DETECTOR_TAG


def test_detector_tag_non_string_is_dropped():
    # Arrange
    fields = {"detector_tag": ["array.push"]}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert "detector_tag" not in out


def test_defect_pattern_tag_truncates_to_max():
    # Arrange
    long = "y" * (audit_log.MAX_DEFECT_PATTERN_TAG + 25)

    # Act
    out = audit_log._normalize_schema({"defect_pattern_tag": long})

    # Assert
    assert len(out["defect_pattern_tag"]) == audit_log.MAX_DEFECT_PATTERN_TAG


def test_defect_pattern_tag_non_string_is_dropped():
    # Arrange
    fields = {"defect_pattern_tag": 12}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert "defect_pattern_tag" not in out


def test_normalize_schema_preserves_unrelated_fields():
    # Arrange
    fields = {"hook": "x", "decision": "block", "reason": "r"}

    # Act
    out = audit_log._normalize_schema(fields)

    # Assert
    assert out == {"hook": "x", "decision": "block", "reason": "r"}


def test_defect_pattern_tags_constant_includes_canonical_set():
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
    "raw,expected_in_output",
    [
        ("AKIAABCDEFGHIJKLMNOP", "[REDACTED]"),
        ("sk-ant-abc123def456ghi789jklmn", "[REDACTED]"),
        ("AIza" + "x" * 35, "[REDACTED]"),
        ("ghp_" + "a" * 36, "[REDACTED]"),
        ("github_pat_" + "a" * 22, "[REDACTED]"),
        ("glpat-" + "x" * 20, "[REDACTED]"),
        ("xoxb-1234567890-abcdefghij", "[REDACTED]"),
        ("hf_" + "a" * 34, "[REDACTED]"),
        ("npm_" + "a" * 36, "[REDACTED]"),
        ("pypi-" + "a" * 16, "[REDACTED]"),
        (
            "eyJabcdefghij.eyJklmnopqrst.signaturefoo",
            "[REDACTED]",
        ),
        ("-----BEGIN RSA PRIVATE KEY-----", "[REDACTED]"),
        ("postgres://user:secret@host:5432/db", "[REDACTED]"),
        ("password='supersecret'", "[REDACTED]"),
    ],
)
def test_redact_replaces_known_patterns(raw, expected_in_output):
    # Arrange
    secret_text = raw

    # Act
    out = audit_log.redact(secret_text)

    # Assert
    assert expected_in_output in out


def test_redact_is_idempotent():
    # Arrange
    once = audit_log.redact("AKIAABCDEFGHIJKLMNOP")

    # Act
    twice = audit_log.redact(once)

    # Assert
    assert once == twice


def test_redact_empty_string_is_returned_as_is():
    # Arrange
    text = ""

    # Act
    out = audit_log.redact(text)

    # Assert
    assert out == ""


def test_redact_none_is_returned_as_is():
    # Arrange
    missing = None

    # Act
    out = audit_log.redact(missing)  # type: ignore[arg-type]

    # Assert
    assert out is None


def test_redact_leaves_non_secret_text_alone():
    # Arrange
    text = "running rm -rf / on a build artifact path"

    # Act
    out = audit_log.redact(text)

    # Assert
    assert out == text


def test_record_redacts_command_excerpt(isolated_log):
    # Arrange
    secret = "AKIAABCDEFGHIJKLMNOP"

    # Act
    audit_log.record(hook="x", decision="block", command_excerpt=f"aws --key {secret}")

    # Assert
    records = _read_records(isolated_log)
    assert len(records) == 1
    assert "[REDACTED]" in records[0]["command_excerpt"]
    assert secret not in records[0]["command_excerpt"]


def test_record_truncates_command_excerpt(isolated_log):
    # Arrange
    long_cmd = "echo " + ("x" * 1000)

    # Act
    audit_log.record(hook="x", decision="allow", command_excerpt=long_cmd)

    # Assert
    records = _read_records(isolated_log)
    assert len(records) == 1
    assert len(records[0]["command_excerpt"]) <= audit_log.MAX_EXCERPT


def test_rotation_triggers_when_log_exceeds_max_bytes(monkeypatch, isolated_log):
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


def test_rotation_replaces_existing_backup(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setattr(audit_log, "MAX_BYTES", 50)
    Path(audit_log.LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(audit_log.BACKUP_PATH).write_text('{"hook":"stale"}\n')
    audit_log.record(hook="primary", decision="allow")

    # Act
    audit_log.record(hook="next", decision="allow")

    # Assert
    backup_records = _read_records(Path(audit_log.BACKUP_PATH))
    assert [r.get("hook") for r in backup_records] == ["primary"]


def test_rotation_no_op_when_log_missing(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setattr(audit_log, "MAX_BYTES", 50)

    # Act
    audit_log._rotate_if_needed()

    # Assert
    assert (isolated_log.exists(), Path(audit_log.BACKUP_PATH).exists()) == (
        False,
        False,
    )


def test_rotation_no_op_when_under_threshold(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setattr(audit_log, "MAX_BYTES", 10_000)
    audit_log.record(hook="small", decision="allow")
    size_before = isolated_log.stat().st_size

    # Act
    audit_log._rotate_if_needed()

    # Assert
    assert isolated_log.stat().st_size == size_before
    assert Path(audit_log.BACKUP_PATH).exists() is False


def test_rotation_swallows_oserror_on_rename(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setattr(audit_log, "MAX_BYTES", 10)
    audit_log.record(hook="boom", decision="allow")
    monkeypatch.setattr(audit_log.os, "rename", fail_rename)

    # Act
    audit_log._rotate_if_needed()

    # Assert
    assert [r["hook"] for r in _read_records(isolated_log)] == ["boom"]
    assert Path(audit_log.BACKUP_PATH).exists() is False


def test_concurrent_writers_produce_intact_lines(isolated_log):
    # Arrange
    writers = 16
    per_writer = 25

    # Act
    _run_concurrent_writers(writers, per_writer)

    # Assert
    records = _read_records(isolated_log)
    assert len(records) == writers * per_writer
    assert [r for r in records if "hook" not in r or "decision" not in r] == []


def test_record_with_no_fields_writes_timestamp_only(isolated_log):
    # Arrange
    log_path = isolated_log

    # Act
    audit_log.record()

    # Assert
    records = _read_records(log_path)
    assert len(records) == 1
    assert "ts" in records[0]


def test_record_swallows_non_serializable_field(isolated_log):
    # Arrange
    class Weird:
        def __str__(self) -> str:
            return "weird-object"

    # Act
    audit_log.record(hook="x", decision="allow", payload=Weird())

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["payload"] == "weird-object"


def test_record_handles_recursive_object_silently(isolated_log):
    # Arrange
    cycle: dict = {}
    cycle["self"] = cycle

    # Act
    audit_log.record(hook="x", decision="allow", payload=cycle)

    # Assert
    assert _read_records(isolated_log) == []


def test_record_silent_when_disable_env_set(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setenv("CLAUDE_HOOK_AUDIT_DISABLE", "1")

    # Act
    audit_log.record(hook="x", decision="allow")

    # Assert
    assert isolated_log.exists() is False


def test_record_swallows_makedirs_oserror(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setattr(audit_log.os, "makedirs", boom)

    # Act
    audit_log.record(hook="x", decision="allow")

    # Assert
    assert isolated_log.exists() is False


def test_record_with_long_detector_tag_writes_truncated(isolated_log):
    # Arrange
    long = "z" * (audit_log.MAX_DETECTOR_TAG * 4)

    # Act
    audit_log.record(hook="x", decision="block", detector_tag=long)

    # Assert
    records = _read_records(isolated_log)
    assert len(records[0]["detector_tag"]) == audit_log.MAX_DETECTOR_TAG


def test_record_normalizes_decision_class_on_write(isolated_log):
    # Arrange
    hook = "x"

    # Act
    audit_log.record(hook=hook, decision_class="invalid-class")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["decision_class"] == "warn"
    assert records[0]["original_decision_class"] == "invalid-class"


def test_record_clamps_confidence_score_on_write(isolated_log):
    # Arrange
    hook = "x"

    # Act
    audit_log.record(hook=hook, decision="allow", confidence_score=99)

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["confidence_score"] == 10


def test_record_autofills_cwd_when_missing(isolated_log):
    # Arrange
    hook = "x"

    # Act
    audit_log.record(hook=hook, decision="allow")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["cwd"] == os.getcwd()


def test_record_autofills_session_id_from_claude_code_env(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "primary-123")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "secondary-456")

    # Act
    audit_log.record(hook="x", decision="allow")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == "primary-123"


def test_record_autofills_session_id_from_env(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "abc-123")

    # Act
    audit_log.record(hook="x", decision="allow")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == "abc-123"


def test_record_falls_back_to_legacy_session_id_env(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setenv("SESSION_ID", "legacy-xyz")

    # Act
    audit_log.record(hook="x", decision="allow")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == "legacy-xyz"


def test_record_explicit_session_id_overrides_env(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "from-env")

    # Act
    audit_log.record(hook="x", decision="allow", session_id="from-caller")

    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == "from-caller"


def test_cli_writes_record_with_legacy_flags(isolated_log):
    # Arrange
    argv = [
        "--hook",
        "large-file-blocker",
        "--decision",
        "block",
        "--tool",
        "Bash",
        "--reason",
        "file > 5MB",
        "--command",
        "echo hello",
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
    assert entry["reason"] == "file > 5MB"
    assert entry["command_excerpt"] == "echo hello"


def test_cli_writes_record_with_new_schema_flags(isolated_log):
    # Arrange
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
        "/repo/src/app.ts",
        "--latency-ms",
        "42",
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
    assert entry["file_path"] == "/repo/src/app.ts"
    assert entry["latency_ms"] == 42


def test_cli_rejects_unknown_decision_class(capsys, isolated_log):
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


def test_cli_rejects_invalid_decision(capsys, isolated_log):
    # Arrange
    argv = ["--hook", "x", "--decision", "wat"]

    # Act
    with pytest.raises(SystemExit) as raised:
        audit_log._cli(argv)

    # Assert
    assert raised.value.code == 2
    assert "invalid choice: 'wat'" in capsys.readouterr().err
    assert _read_records(isolated_log) == []


def test_cli_main_entrypoint_runs(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setattr(
        audit_log.sys,
        "argv",
        ["audit_log.py", "--hook", "x", "--decision", "allow"],
    )

    # Act
    rc = audit_log._cli(sys.argv[1:])

    # Assert
    assert rc == 0


def test_module_can_be_imported_repeatedly():
    # Arrange
    module = audit_log

    # Act
    reloaded = importlib.reload(module)

    # Assert
    assert (
        reloaded.MAX_BYTES,
        reloaded.MAX_DETECTOR_TAG,
        reloaded.MAX_DEFECT_PATTERN_TAG,
    ) == (5 * 1024 * 1024, 80, 64)

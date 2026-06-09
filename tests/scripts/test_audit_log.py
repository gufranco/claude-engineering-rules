"""Tests for `scripts/audit_log.py`.
Covers:
  - Schema normalization (decision_class, confidence_score, detector_tag,
    defect_pattern_tag)
  - Redaction of high-precision token patterns
  - Rotation when LOG_PATH crosses MAX_BYTES
  - Lock contention with concurrent writers
  - Malformed input (non-dict, non-serializable, oversized)
  - CLI parsing (legacy flags + new schema flags)
  - CLAUDE_HOOK_AUDIT_DISABLE env switch
  - Auto-fill of cwd and session_id
"""
from __future__ import annotations
import importlib
import json
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
    """Redirect LOG_DIR/LOG_PATH/BACKUP_PATH to a temp directory.
    Returns the active LOG_PATH so tests can read records back without
    leaking into the real ~/.claude/logs/hooks.log.
    """
    log_dir = tmp_path / "logs"
    log_path = log_dir / "hooks.log"
    backup_path = log_dir / "hooks.log.1"
    monkeypatch.setattr(audit_log, "LOG_DIR", str(log_dir))
    monkeypatch.setattr(audit_log, "LOG_PATH", str(log_path))
    monkeypatch.setattr(audit_log, "BACKUP_PATH", str(backup_path))
    monkeypatch.delenv("CLAUDE_HOOK_AUDIT_DISABLE", raising=False)
    return log_path
def _read_records(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [
        json.loads(line) for line in log_path.read_text().splitlines() if line.strip()
    ]
# --------------------------------------------------------------------------- #
# Schema normalization (1.3.1)
# --------------------------------------------------------------------------- #
def test_decision_class_passthrough_when_valid():
    # Arrange/Act
    out = audit_log._normalize_schema({"decision_class": "block"})
    # Assert
    assert out["decision_class"] == "block"
    assert "original_decision_class" not in out
@pytest.mark.parametrize(
    "valid_class",
    sorted(audit_log.ALLOWED_DECISION_CLASSES),
)
def test_each_allowed_decision_class_is_preserved(valid_class):
    # Arrange/Act
    out = audit_log._normalize_schema({"decision_class": valid_class})
    # Assert
    assert out["decision_class"] == valid_class
    assert "original_decision_class" not in out
def test_decision_class_invalid_string_is_demoted_to_warn():
    # Arrange/Act
    out = audit_log._normalize_schema({"decision_class": "wat"})
    # Assert
    assert out["decision_class"] == "warn"
    assert out["original_decision_class"] == "wat"
def test_decision_class_non_string_is_demoted_to_warn():
    # Arrange/Act
    out = audit_log._normalize_schema({"decision_class": 42})
    # Assert
    assert out["decision_class"] == "warn"
    assert out["original_decision_class"] == 42
def test_confidence_score_clamps_high():
    # Arrange/Act
    out = audit_log._normalize_schema({"confidence_score": 99})
    # Assert
    assert out["confidence_score"] == 10
def test_confidence_score_clamps_low():
    # Arrange/Act
    out = audit_log._normalize_schema({"confidence_score": -3})
    # Assert
    assert out["confidence_score"] == 1
def test_confidence_score_inside_range_passes_through():
    # Arrange/Act
    out = audit_log._normalize_schema({"confidence_score": 7})
    # Assert
    assert out["confidence_score"] == 7
def test_confidence_score_string_int_is_coerced():
    # Arrange/Act
    out = audit_log._normalize_schema({"confidence_score": "5"})
    # Assert
    assert out["confidence_score"] == 5
def test_confidence_score_non_numeric_is_dropped():
    # Arrange/Act
    out = audit_log._normalize_schema({"confidence_score": "abc"})
    # Assert
    assert "confidence_score" not in out
def test_confidence_score_none_is_dropped():
    # Arrange/Act
    out = audit_log._normalize_schema({"confidence_score": None})
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
    # Arrange/Act
    out = audit_log._normalize_schema({"detector_tag": ["array.push"]})
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
    # Arrange/Act
    out = audit_log._normalize_schema({"defect_pattern_tag": 12})
    # Assert
    assert "defect_pattern_tag" not in out
def test_normalize_schema_preserves_unrelated_fields():
    # Arrange/Act
    out = audit_log._normalize_schema({"hook": "x", "decision": "block", "reason": "r"})
    # Assert
    assert out == {"hook": "x", "decision": "block", "reason": "r"}
def test_defect_pattern_tags_constant_includes_canonical_set():
    # Assert
    assert "plausible-hallucination" in audit_log.DEFECT_PATTERN_TAGS
    assert "optimistic-error-handling" in audit_log.DEFECT_PATTERN_TAGS
    assert "shallow-validation" in audit_log.DEFECT_PATTERN_TAGS
    assert "copy-paste-drift" in audit_log.DEFECT_PATTERN_TAGS
    assert "missing-cleanup" in audit_log.DEFECT_PATTERN_TAGS
    assert "invented-api" in audit_log.DEFECT_PATTERN_TAGS
# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #
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
    # Arrange/Act
    out = audit_log.redact(raw)
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
    # Arrange/Act
    out = audit_log.redact("")
    # Assert
    assert out == ""
def test_redact_none_is_returned_as_is():
    # Arrange/Act
    out = audit_log.redact(None)  # type: ignore[arg-type]
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
    assert records
    assert "[REDACTED]" in records[0]["command_excerpt"]
    assert secret not in records[0]["command_excerpt"]
def test_record_truncates_command_excerpt(isolated_log):
    # Arrange
    long_cmd = "echo " + ("x" * 1000)
    # Act
    audit_log.record(hook="x", decision="allow", command_excerpt=long_cmd)
    # Assert
    records = _read_records(isolated_log)
    assert records
    assert len(records[0]["command_excerpt"]) <= audit_log.MAX_EXCERPT
# --------------------------------------------------------------------------- #
# Rotation
# --------------------------------------------------------------------------- #
def test_rotation_triggers_when_log_exceeds_max_bytes(monkeypatch, isolated_log):
    # Arrange: shrink MAX_BYTES so a single small record forces rotation
    monkeypatch.setattr(audit_log, "MAX_BYTES", 50)
    audit_log.record(hook="first", decision="allow")
    assert isolated_log.exists()
    # Act: subsequent record should rotate the previous file
    audit_log.record(hook="second", decision="allow")
    # Assert
    backup = Path(audit_log.BACKUP_PATH)
    assert backup.exists(), "expected hooks.log.1 to be created on rotation"
    backup_records = _read_records(backup)
    current_records = _read_records(isolated_log)
    assert any(r["hook"] == "first" for r in backup_records)
    assert any(r["hook"] == "second" for r in current_records)
def test_rotation_replaces_existing_backup(monkeypatch, isolated_log):
    # Arrange: pre-create a stale backup file
    monkeypatch.setattr(audit_log, "MAX_BYTES", 50)
    Path(audit_log.LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(audit_log.BACKUP_PATH).write_text('{"hook":"stale"}\n')
    audit_log.record(hook="primary", decision="allow")
    assert isolated_log.exists()
    # Act
    audit_log.record(hook="next", decision="allow")
    # Assert: stale backup is overwritten by the previous primary log
    backup_records = _read_records(Path(audit_log.BACKUP_PATH))
    assert any(r.get("hook") == "primary" for r in backup_records)
    assert not any(r.get("hook") == "stale" for r in backup_records)
def test_rotation_no_op_when_log_missing(monkeypatch, isolated_log):
    # Arrange: log path does not exist yet
    monkeypatch.setattr(audit_log, "MAX_BYTES", 50)
    assert not isolated_log.exists()
    # Act
    audit_log._rotate_if_needed()
    # Assert: no exception, no backup created
    assert not Path(audit_log.BACKUP_PATH).exists()
def test_rotation_no_op_when_under_threshold(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setattr(audit_log, "MAX_BYTES", 10_000)
    audit_log.record(hook="small", decision="allow")
    size_before = isolated_log.stat().st_size
    # Act
    audit_log._rotate_if_needed()
    # Assert: log file unchanged, no backup
    assert isolated_log.stat().st_size == size_before
    assert not Path(audit_log.BACKUP_PATH).exists()
def test_rotation_swallows_oserror_on_rename(monkeypatch, isolated_log):
    # Arrange: rotation must trigger
    monkeypatch.setattr(audit_log, "MAX_BYTES", 10)
    audit_log.record(hook="boom", decision="allow")
    def fail_rename(*_args, **_kwargs):
        raise OSError("simulated cross-device rename failure")
    monkeypatch.setattr(audit_log.os, "rename", fail_rename)
    # Act/Assert: must not raise
    audit_log._rotate_if_needed()
# --------------------------------------------------------------------------- #
# Lock contention
# --------------------------------------------------------------------------- #
def test_concurrent_writers_produce_intact_lines(isolated_log):
    # Arrange
    writers = 16
    per_writer = 25
    expected_total = writers * per_writer
    def worker(idx: int) -> None:
        for n in range(per_writer):
            audit_log.record(hook=f"w{idx}", decision="allow", reason=f"r-{idx}-{n}")
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(writers)]
    # Act
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Assert: every line parses and the expected count is present
    records = _read_records(isolated_log)
    assert len(records) == expected_total
    for r in records:
        assert "hook" in r and "decision" in r
# --------------------------------------------------------------------------- #
# Malformed input
# --------------------------------------------------------------------------- #
def test_record_with_no_fields_writes_timestamp_only(isolated_log):
    # Arrange/Act
    audit_log.record()
    # Assert
    records = _read_records(isolated_log)
    assert len(records) == 1
    assert "ts" in records[0]
def test_record_swallows_non_serializable_field(isolated_log):
    # Arrange: the JSON encoder uses default=str so unusual objects round-trip
    class Weird:
        def __str__(self) -> str:
            return "weird-object"
    # Act
    audit_log.record(hook="x", decision="allow", payload=Weird())
    # Assert
    records = _read_records(isolated_log)
    assert records[0]["payload"] == "weird-object"
def test_record_handles_recursive_object_silently(isolated_log):
    # Arrange: a self-referential dict cannot serialize even with default=str
    cycle: dict = {}
    cycle["self"] = cycle
    # Act/Assert: must not raise
    audit_log.record(hook="x", decision="allow", payload=cycle)
def test_record_silent_when_disable_env_set(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setenv("CLAUDE_HOOK_AUDIT_DISABLE", "1")
    # Act
    audit_log.record(hook="x", decision="allow")
    # Assert
    assert not isolated_log.exists()
def test_record_swallows_makedirs_oserror(monkeypatch, isolated_log):
    # Arrange
    def boom(*_args, **_kwargs):
        raise OSError("readonly fs")
    monkeypatch.setattr(audit_log.os, "makedirs", boom)
    # Act/Assert: must not raise, log file not created
    audit_log.record(hook="x", decision="allow")
    assert not isolated_log.exists()
def test_record_with_long_detector_tag_writes_truncated(isolated_log):
    # Arrange
    long = "z" * (audit_log.MAX_DETECTOR_TAG * 4)
    # Act
    audit_log.record(hook="x", decision="block", detector_tag=long)
    # Assert
    records = _read_records(isolated_log)
    assert len(records[0]["detector_tag"]) == audit_log.MAX_DETECTOR_TAG
def test_record_normalizes_decision_class_on_write(isolated_log):
    # Arrange/Act
    audit_log.record(hook="x", decision_class="invalid-class")
    # Assert
    records = _read_records(isolated_log)
    assert records[0]["decision_class"] == "warn"
    assert records[0]["original_decision_class"] == "invalid-class"
def test_record_clamps_confidence_score_on_write(isolated_log):
    # Arrange/Act
    audit_log.record(hook="x", decision="allow", confidence_score=99)
    # Assert
    records = _read_records(isolated_log)
    assert records[0]["confidence_score"] == 10
def test_record_autofills_cwd_when_missing(isolated_log):
    # Arrange/Act
    audit_log.record(hook="x", decision="allow")
    # Assert
    records = _read_records(isolated_log)
    assert "cwd" in records[0]
    assert records[0]["cwd"]
def test_record_autofills_session_id_from_env(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setenv("CLAUDE_SESSION_ID", "abc-123")
    # Act
    audit_log.record(hook="x", decision="allow")
    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == "abc-123"
def test_record_falls_back_to_legacy_session_id_env(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setenv("SESSION_ID", "legacy-xyz")
    # Act
    audit_log.record(hook="x", decision="allow")
    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == "legacy-xyz"
def test_record_explicit_session_id_overrides_env(monkeypatch, isolated_log):
    # Arrange
    monkeypatch.setenv("CLAUDE_SESSION_ID", "from-env")
    # Act
    audit_log.record(hook="x", decision="allow", session_id="from-caller")
    # Assert
    records = _read_records(isolated_log)
    assert records[0]["session_id"] == "from-caller"
# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
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
    assert records
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
    # Act/Assert
    with pytest.raises(SystemExit):
        audit_log._cli(argv)
def test_cli_rejects_invalid_decision(capsys, isolated_log):
    # Arrange
    argv = ["--hook", "x", "--decision", "wat"]
    # Act/Assert
    with pytest.raises(SystemExit):
        audit_log._cli(argv)
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
    # Arrange/Act/Assert: re-importing must not change identity of constants
    importlib.reload(audit_log)
    assert audit_log.MAX_BYTES == 5 * 1024 * 1024
    assert audit_log.MAX_DETECTOR_TAG == 80
    assert audit_log.MAX_DEFECT_PATTERN_TAG == 64

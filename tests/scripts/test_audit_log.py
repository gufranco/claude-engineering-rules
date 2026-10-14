from __future__ import annotations


import pytest
from faker import Faker

from _helpers.audit_log_support import (
    AWS_STYLE_KEY,
    DEFECT_PATTERN_TAG_LIMIT,
    DETECTOR_TAG_LIMIT,
    REDACTED,
    audit_log,
)


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

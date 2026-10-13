from __future__ import annotations

import sys
from pathlib import Path

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_project_config as mpc  # noqa: E402


def test_discover_config_path_returns_none_when_claude_dir_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    # Act
    result = mpc.discover_config_path(str(tmp_path))

    # Assert
    assert result is None


def test_parse_yaml_minimal_skips_blank_and_comment_lines() -> None:
    # Arrange
    text = "\n# top comment\nversion: 1\n\n# trailing\n"

    # Act
    data = mpc._parse_yaml_minimal(text)

    # Assert
    assert data == {"version": 1}


def test_parse_yaml_minimal_raises_on_orphan_list_item(faker: Faker) -> None:
    # Arrange
    text = f"  - {faker.word()}"

    # Act
    with pytest.raises(ValueError) as raised:
        mpc._parse_yaml_minimal(text)

    # Assert
    assert "unexpected list item" in str(raised.value)


def test_parse_yaml_minimal_raises_on_missing_colon(faker: Faker) -> None:
    # Arrange
    text = faker.word()

    # Act
    with pytest.raises(ValueError) as raised:
        mpc._parse_yaml_minimal(text)

    # Assert
    assert "missing colon" in str(raised.value)


def test_parse_yaml_minimal_strips_quotes_from_scalar_string(faker: Faker) -> None:
    # Arrange
    value = faker.word()
    text = f'name: "{value}"'

    # Act
    data = mpc._parse_yaml_minimal(text)

    # Assert
    assert data == {"name": value}


def test_load_text_returns_none_on_os_error(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    unreadable = tmp_path / f"{faker.word()}.json"
    unreadable.mkdir()

    # Act
    result = mpc._load_text(str(unreadable))

    # Assert
    captured = capsys.readouterr()
    assert result is None
    assert "unable to read" in captured.err


def test_load_text_returns_none_for_non_dict_top_level(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    # Act
    result = mpc._load_text(str(path))

    # Assert
    captured = capsys.readouterr()
    assert result is None
    assert "is not a mapping" in captured.err


def _install_fake_jsonschema(monkeypatch: pytest.MonkeyPatch) -> type[Exception]:
    import types

    fake = types.ModuleType("jsonschema")

    class ValidationError(Exception):
        def __init__(self, message: str) -> None:
            super().__init__(message)
            self.message = message

    def validate(data: object, schema: object) -> None:  # noqa: ARG001
        if isinstance(data, dict) and data.get("__force_invalid__"):
            raise ValidationError("forced invalid")

    fake.ValidationError = ValidationError
    fake.validate = validate
    monkeypatch.setitem(sys.modules, "jsonschema", fake)
    return ValidationError


def test_validate_with_jsonschema_falls_back_when_schema_file_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    _install_fake_jsonschema(monkeypatch)
    monkeypatch.setattr(mpc, "SCHEMA_PATH", str(tmp_path / f"{faker.word()}.json"))

    # Act
    result = mpc._validate_with_jsonschema({"version": 1})

    # Assert
    assert result is True


def test_validate_with_jsonschema_falls_back_on_schema_decode_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _install_fake_jsonschema(monkeypatch)
    bad_schema = tmp_path / "schema.json"
    bad_schema.write_text("not json {", encoding="utf-8")
    monkeypatch.setattr(mpc, "SCHEMA_PATH", str(bad_schema))

    # Act
    result = mpc._validate_with_jsonschema({"version": 1})

    # Assert
    captured = capsys.readouterr()
    assert result is True
    assert "unable to load schema" in captured.err


def test_validate_with_jsonschema_returns_false_on_validation_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _install_fake_jsonschema(monkeypatch)
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mpc, "SCHEMA_PATH", str(schema_path))

    # Act
    result = mpc._validate_with_jsonschema({"version": 1, "__force_invalid__": True})

    # Assert
    captured = capsys.readouterr()
    assert result is False
    assert "validation failed" in captured.err


def test_validate_with_jsonschema_returns_true_on_valid_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _install_fake_jsonschema(monkeypatch)
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mpc, "SCHEMA_PATH", str(schema_path))

    # Act
    result = mpc._validate_with_jsonschema({"version": 1})

    # Assert
    assert result is True


def test_validate_with_jsonschema_falls_back_when_jsonschema_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setitem(sys.modules, "jsonschema", None)

    # Act
    result = mpc._validate_with_jsonschema({"version": 1})

    # Assert
    assert result is True


def test_validate_inline_rejects_empty_string_item(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    data = {"version": 1, "framework_receivers": [""]}

    # Act
    result = mpc._validate_inline(data)

    # Assert
    captured = capsys.readouterr()
    assert result is False
    assert "non-string or empty item" in captured.err


def test_validate_inline_rejects_non_string_item(
    capsys: pytest.CaptureFixture[str], faker: Faker
) -> None:
    # Arrange
    data = {"version": 1, "framework_receivers": [faker.random_int()]}

    # Act
    result = mpc._validate_inline(data)

    # Assert
    captured = capsys.readouterr()
    assert result is False
    assert "non-string or empty item" in captured.err


def test_load_project_config_returns_empty_for_empty_start_path() -> None:
    # Arrange
    start_path = ""

    # Act
    config = mpc.load_project_config(start_path)

    # Assert
    assert config is mpc.EMPTY_CONFIG

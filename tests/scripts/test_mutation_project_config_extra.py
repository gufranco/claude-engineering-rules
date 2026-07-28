"""Extra coverage for `scripts/mutation_project_config.py`.

Targets the YAML parser edge cases, the OSError path in `_load_text`,
the jsonschema fallback chain, the inline-validator failure modes, and
the empty-start-path early return.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_project_config as mpc  # noqa: E402


# --------------------------------------------------------------------------- #
# discover_config_path (line 92)
# --------------------------------------------------------------------------- #


def test_discover_config_path_returns_none_when_claude_dir_missing(
    tmp_path: Path,
) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    result = mpc.discover_config_path(str(tmp_path))

    assert result is None


# --------------------------------------------------------------------------- #
# _parse_yaml_minimal (lines 118, 121, 130, 144)
# --------------------------------------------------------------------------- #


def test_parse_yaml_minimal_skips_blank_and_comment_lines() -> None:
    text = "\n# top comment\nversion: 1\n\n# trailing\n"

    data = mpc._parse_yaml_minimal(text)

    assert data == {"version": 1}


def test_parse_yaml_minimal_raises_on_orphan_list_item() -> None:
    text = "  - bareItem"

    with pytest.raises(ValueError, match="unexpected list item"):
        mpc._parse_yaml_minimal(text)


def test_parse_yaml_minimal_raises_on_missing_colon() -> None:
    text = "noColonHere"

    with pytest.raises(ValueError, match="missing colon"):
        mpc._parse_yaml_minimal(text)


def test_parse_yaml_minimal_strips_quotes_from_scalar_string() -> None:
    text = 'name: "value"'

    data = mpc._parse_yaml_minimal(text)

    assert data == {"name": "value"}


# --------------------------------------------------------------------------- #
# _load_text OSError + non-dict (lines 152-154, 168-169)
# --------------------------------------------------------------------------- #


def test_load_text_returns_none_on_os_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("builtins.open", side_effect=OSError("permission denied")):
        result = mpc._load_text("/some/path.json")
        captured = capsys.readouterr()

    assert result is None
    assert "unable to read" in captured.err


def test_load_text_returns_none_for_non_dict_top_level(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    result = mpc._load_text(str(path))
    captured = capsys.readouterr()

    assert result is None
    assert "is not a mapping" in captured.err


# --------------------------------------------------------------------------- #
# _validate_with_jsonschema fallbacks (lines 178-191)
# --------------------------------------------------------------------------- #


def _install_fake_jsonschema(monkeypatch) -> type:
    """Inject a minimal fake `jsonschema` module so the branch that imports
    it inside `_validate_with_jsonschema` succeeds. Returns the
    `ValidationError` class so callers can raise it to trigger validation
    failure paths.
    """
    import types

    fake = types.ModuleType("jsonschema")

    class ValidationError(Exception):
        def __init__(self, message: str) -> None:
            super().__init__(message)
            self.message = message

    def validate(data, schema):  # noqa: ARG001
        if isinstance(data, dict) and data.get("__force_invalid__"):
            raise ValidationError("forced invalid")

    fake.ValidationError = ValidationError
    fake.validate = validate
    monkeypatch.setitem(sys.modules, "jsonschema", fake)
    return ValidationError


def test_validate_with_jsonschema_falls_back_when_schema_file_missing(
    monkeypatch,
) -> None:
    _install_fake_jsonschema(monkeypatch)
    monkeypatch.setattr(mpc, "SCHEMA_PATH", "/nonexistent/schema.json")

    result = mpc._validate_with_jsonschema({"version": 1})

    assert result is True


def test_validate_with_jsonschema_falls_back_on_schema_decode_error(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_fake_jsonschema(monkeypatch)
    bad_schema = tmp_path / "schema.json"
    bad_schema.write_text("not json {", encoding="utf-8")
    monkeypatch.setattr(mpc, "SCHEMA_PATH", str(bad_schema))

    result = mpc._validate_with_jsonschema({"version": 1})
    captured = capsys.readouterr()

    assert result is True
    assert "unable to load schema" in captured.err


def test_validate_with_jsonschema_returns_false_on_validation_error(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # sentinel field the fake module checks.
    _install_fake_jsonschema(monkeypatch)
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mpc, "SCHEMA_PATH", str(schema_path))

    result = mpc._validate_with_jsonschema({"version": 1, "__force_invalid__": True})
    captured = capsys.readouterr()

    assert result is False
    assert "validation failed" in captured.err


def test_validate_with_jsonschema_returns_true_on_valid_schema(
    monkeypatch, tmp_path: Path
) -> None:
    _install_fake_jsonschema(monkeypatch)
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mpc, "SCHEMA_PATH", str(schema_path))

    result = mpc._validate_with_jsonschema({"version": 1})

    assert result is True


def test_validate_with_jsonschema_falls_back_when_jsonschema_missing(
    monkeypatch,
) -> None:
    monkeypatch.setitem(sys.modules, "jsonschema", None)

    result = mpc._validate_with_jsonschema({"version": 1})

    assert result is True


# --------------------------------------------------------------------------- #
# _validate_inline non-string / empty item (lines 217-218)
# --------------------------------------------------------------------------- #


def test_validate_inline_rejects_empty_string_item(
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = {"version": 1, "framework_receivers": [""]}

    result = mpc._validate_inline(data)
    captured = capsys.readouterr()

    assert result is False
    assert "non-string or empty item" in captured.err


def test_validate_inline_rejects_non_string_item(
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = {"version": 1, "framework_receivers": [123]}

    result = mpc._validate_inline(data)
    captured = capsys.readouterr()

    assert result is False
    assert "non-string or empty item" in captured.err


# --------------------------------------------------------------------------- #
# load_project_config empty start_path (line 241)
# --------------------------------------------------------------------------- #


def test_load_project_config_returns_empty_for_empty_start_path() -> None:
    config = mpc.load_project_config("")

    assert config is mpc.EMPTY_CONFIG

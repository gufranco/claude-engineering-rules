"""Project-local config loader tests.

Plan items 284-287. Verifies `scripts/mutation_project_config.py`:

  - Discovers a project root via `.git`, `package.json`, or
    `pnpm-workspace.yaml`.
  - Loads YAML and JSON config files from `<root>/.claude/`.
  - Returns `EMPTY_CONFIG` for missing or malformed configs without
    raising.
  - Schema validation rejects bad version / non-list field types.
  - Unknown fields produce a warning and are ignored, never an error.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

from _lib import mutation_project_config as mpc  # noqa: E402


def _make_project(tmp_path: Path, marker: str = "package.json") -> Path:
    """Create a minimal project root containing the given marker."""
    if marker == ".git":
        (tmp_path / ".git").mkdir()
    else:
        (tmp_path / marker).write_text("{}\n", encoding="utf-8")
    (tmp_path / ".claude").mkdir()
    return tmp_path


def test_empty_config_when_no_project_root(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "isolated" / "src" / "a.ts"
    sub.parent.mkdir(parents=True)
    sub.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(sub))
    # Assert
    assert config is mpc.EMPTY_CONFIG


def test_empty_config_when_marker_present_but_no_config(tmp_path: Path) -> None:
    # Arrange
    root = _make_project(tmp_path)
    src = root / "src" / "a.ts"
    src.parent.mkdir(parents=True)
    src.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(src))
    # Assert
    assert config is mpc.EMPTY_CONFIG


def test_loads_yaml_with_lists(tmp_path: Path) -> None:
    # Arrange
    root = _make_project(tmp_path)
    cfg = root / ".claude" / "mutation-allowlist.yml"
    cfg.write_text(
        """version: 1
framework_receivers:
  - customRouter
  - eventBus
hot_path_segments:
  - /matrices/
disable_detectors:
  - array.push
""",
        encoding="utf-8",
    )
    src = root / "src" / "a.ts"
    src.parent.mkdir(parents=True)
    src.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(src))
    # Assert
    assert "customRouter" in config.framework_receivers
    assert "eventBus" in config.framework_receivers
    assert config.hot_path_segments == ("/matrices/",)
    assert "array.push" in config.disable_detectors


def test_loads_json_config(tmp_path: Path) -> None:
    # Arrange
    root = _make_project(tmp_path, marker=".git")
    cfg = root / ".claude" / "mutation-allowlist.json"
    cfg.write_text(
        json.dumps(
            {
                "version": 1,
                "framework_receivers": ["customStream"],
                "experimental_detectors": ["OPTIONAL_CHAIN_ASSIGN"],
            }
        ),
        encoding="utf-8",
    )
    src = root / "lib" / "x.ts"
    src.parent.mkdir(parents=True)
    src.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(src))
    # Assert
    assert "customStream" in config.framework_receivers
    assert "OPTIONAL_CHAIN_ASSIGN" in config.experimental_detectors


def test_invalid_version_returns_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    root = _make_project(tmp_path)
    cfg = root / ".claude" / "mutation-allowlist.json"
    cfg.write_text(json.dumps({"version": 2}), encoding="utf-8")
    src = root / "src" / "a.ts"
    src.parent.mkdir(parents=True)
    src.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(src))
    # Assert
    assert config is mpc.EMPTY_CONFIG
    err = capsys.readouterr().err
    assert "version" in err.lower()


def test_malformed_json_returns_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    root = _make_project(tmp_path)
    cfg = root / ".claude" / "mutation-allowlist.json"
    cfg.write_text("{not json", encoding="utf-8")
    src = root / "src" / "a.ts"
    src.parent.mkdir(parents=True)
    src.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(src))
    # Assert
    assert config is mpc.EMPTY_CONFIG
    err = capsys.readouterr().err
    assert "JSON" in err or "invalid" in err.lower()


def test_unknown_fields_warn_but_dont_fail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    # Arrange
    monkeypatch.setattr(mpc, "_validate_with_jsonschema", mpc._validate_inline)
    root = _make_project(tmp_path)
    cfg = root / ".claude" / "mutation-allowlist.json"
    cfg.write_text(
        json.dumps(
            {
                "version": 1,
                "framework_receivers": ["okay"],
                "future_field": ["ignored"],
            }
        ),
        encoding="utf-8",
    )
    src = root / "src" / "a.ts"
    src.parent.mkdir(parents=True)
    src.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(src))
    # Assert
    assert "okay" in config.framework_receivers
    err = capsys.readouterr().err
    assert "unknown" in err.lower()


def test_non_list_field_returns_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    # Arrange
    monkeypatch.setattr(mpc, "_validate_with_jsonschema", mpc._validate_inline)
    root = _make_project(tmp_path)
    cfg = root / ".claude" / "mutation-allowlist.json"
    cfg.write_text(
        json.dumps({"version": 1, "framework_receivers": "not-a-list"}),
        encoding="utf-8",
    )
    src = root / "src" / "a.ts"
    src.parent.mkdir(parents=True)
    src.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(src))
    # Assert
    assert config is mpc.EMPTY_CONFIG
    err = capsys.readouterr().err
    assert "list" in err.lower()


def test_discover_project_root_walks_up(tmp_path: Path) -> None:
    # Arrange
    root = _make_project(tmp_path)
    deep = root / "src" / "modules" / "feature" / "a.ts"
    deep.parent.mkdir(parents=True)
    deep.write_text("", encoding="utf-8")
    # Act
    discovered = mpc.discover_project_root(str(deep))
    # Assert
    assert discovered is not None
    assert os.path.realpath(discovered) == os.path.realpath(str(root))


def test_yaml_empty_file_treated_as_no_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    # Arrange
    monkeypatch.setattr(mpc, "_validate_with_jsonschema", mpc._validate_inline)
    root = _make_project(tmp_path)
    cfg = root / ".claude" / "mutation-allowlist.yml"
    cfg.write_text("", encoding="utf-8")
    src = root / "src" / "a.ts"
    src.parent.mkdir(parents=True)
    src.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(src))
    # Assert
    assert config is mpc.EMPTY_CONFIG


def test_yaml_with_unsupported_indentation_returns_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    root = _make_project(tmp_path)
    cfg = root / ".claude" / "mutation-allowlist.yml"
    cfg.write_text(
        "version: 1\nframework_receivers:\n    nested: 1\n", encoding="utf-8"
    )
    src = root / "src" / "a.ts"
    src.parent.mkdir(parents=True)
    src.write_text("", encoding="utf-8")
    # Act
    config = mpc.load_project_config(str(src))
    # Assert
    assert config is mpc.EMPTY_CONFIG

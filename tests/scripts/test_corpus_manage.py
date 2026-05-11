"""Tests for `scripts/corpus_manage.py`.

Covers fixture listing, addition, validation pass/fail aggregation, and
VERSION file regeneration.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import corpus_manage as cm  # noqa: E402


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def corpus_root(tmp_path: Path, monkeypatch) -> Path:
    """Redirect CORPUS_ROOT and VERSION_FILE under tmp_path."""
    root = tmp_path / "corpus"
    root.mkdir()
    monkeypatch.setattr(cm, "CORPUS_ROOT", str(root))
    monkeypatch.setattr(cm, "VERSION_FILE", str(root / "VERSION"))
    return root


# --------------------------------------------------------------------------- #
# _list_fixtures
# --------------------------------------------------------------------------- #


def test_list_fixtures_empty_when_root_missing(monkeypatch, tmp_path: Path) -> None:
    # Arrange
    monkeypatch.setattr(cm, "CORPUS_ROOT", str(tmp_path / "missing"))

    # Act
    fixtures = cm._list_fixtures()

    # Assert
    assert fixtures == []


def test_list_fixtures_categorizes_clean_dirty_unknown(corpus_root: Path) -> None:
    # Arrange
    cat = corpus_root / "category-a"
    cat.mkdir()
    (cat / "clean.ts").write_text("ok", encoding="utf-8")
    (cat / "dirty.tsx").write_text("ok", encoding="utf-8")
    (cat / "other.ts").write_text("ok", encoding="utf-8")
    (cat / "skip.txt").write_text("ignore", encoding="utf-8")
    (corpus_root / "non-dir.txt").write_text("ignore", encoding="utf-8")

    # Act
    fixtures = cm._list_fixtures()

    # Assert
    by_name = {fx.relpath: fx.expected for fx in fixtures}
    assert "category-a/clean.ts" in by_name
    assert by_name["category-a/clean.ts"] == "clean"
    assert by_name["category-a/dirty.tsx"] == "dirty"
    assert by_name["category-a/other.ts"] == "unknown"


def test_fixture_display_returns_category_and_basename() -> None:
    # Arrange
    fixture = cm.Fixture(
        category="cat",
        relpath="cat/clean.ts",
        abspath="/abs/cat/clean.ts",
        expected="clean",
    )

    # Act
    display = fixture.display

    # Assert
    assert display == "cat/clean.ts"


# --------------------------------------------------------------------------- #
# _expected_pass
# --------------------------------------------------------------------------- #


def test_expected_pass_clean_zero_exit() -> None:
    assert cm._expected_pass(0, "", "clean") is True
    assert cm._expected_pass(2, "", "clean") is False


def test_expected_pass_dirty_block_exit() -> None:
    assert cm._expected_pass(2, "", "dirty") is True


def test_expected_pass_dirty_blocked_in_stderr() -> None:
    assert cm._expected_pass(0, "Blocked: array.push", "dirty") is True
    assert cm._expected_pass(0, "blocked: x", "dirty") is True


def test_expected_pass_unknown_returns_false() -> None:
    assert cm._expected_pass(0, "", "unknown") is False


# --------------------------------------------------------------------------- #
# _cmd_list
# --------------------------------------------------------------------------- #


def test_cmd_list_empty_corpus_returns_zero(corpus_root: Path, capsys) -> None:
    # Arrange
    args = MagicMock()

    # Act
    rc = cm._cmd_list(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "(corpus empty)" in captured.out


def test_cmd_list_with_fixtures_prints_summary(corpus_root: Path, capsys) -> None:
    # Arrange
    cat = corpus_root / "demo"
    cat.mkdir()
    (cat / "clean.ts").write_text("ok", encoding="utf-8")
    args = MagicMock()

    # Act
    rc = cm._cmd_list(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "Fixture count: 1" in captured.out
    assert "demo/clean.ts" in captured.out


# --------------------------------------------------------------------------- #
# _cmd_add
# --------------------------------------------------------------------------- #


def test_cmd_add_missing_file_returns_one(
    corpus_root: Path, capsys, tmp_path: Path
) -> None:
    # Arrange
    args = MagicMock()
    args.file = str(tmp_path / "missing.ts")
    args.category = "demo"
    args.expected = "clean"

    # Act
    rc = cm._cmd_add(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 1
    assert "file not found" in captured.err


def test_cmd_add_invalid_expected_returns_one(
    corpus_root: Path, capsys, tmp_path: Path
) -> None:
    # Arrange
    src = tmp_path / "src.ts"
    src.write_text("ok", encoding="utf-8")
    args = MagicMock()
    args.file = str(src)
    args.category = "demo"
    args.expected = "weird"

    # Act
    rc = cm._cmd_add(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 1
    assert "expected must be" in captured.err


def test_cmd_add_unsupported_extension_returns_one(
    corpus_root: Path, capsys, tmp_path: Path
) -> None:
    # Arrange
    src = tmp_path / "src.py"
    src.write_text("ok", encoding="utf-8")
    args = MagicMock()
    args.file = str(src)
    args.category = "demo"
    args.expected = "clean"

    # Act
    rc = cm._cmd_add(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 1
    assert "unsupported extension" in captured.err


def test_cmd_add_creates_target_under_category(
    corpus_root: Path, capsys, tmp_path: Path
) -> None:
    # Arrange
    src = tmp_path / "src.ts"
    src.write_text("ok", encoding="utf-8")
    args = MagicMock()
    args.file = str(src)
    args.category = "demo"
    args.expected = "clean"

    # Act
    rc = cm._cmd_add(args)

    # Assert
    assert rc == 0
    assert (corpus_root / "demo" / "clean.ts").exists()


def test_cmd_add_refuses_to_overwrite(
    corpus_root: Path, capsys, tmp_path: Path
) -> None:
    # Arrange
    cat = corpus_root / "demo"
    cat.mkdir()
    (cat / "clean.ts").write_text("existing", encoding="utf-8")
    src = tmp_path / "src.ts"
    src.write_text("new", encoding="utf-8")
    args = MagicMock()
    args.file = str(src)
    args.category = "demo"
    args.expected = "clean"

    # Act
    rc = cm._cmd_add(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 1
    assert "target already exists" in captured.err


# --------------------------------------------------------------------------- #
# _cmd_validate
# --------------------------------------------------------------------------- #


def test_cmd_validate_empty_corpus_returns_one(corpus_root: Path, capsys) -> None:
    # Arrange
    args = MagicMock()
    args.fail_under = None

    # Act
    rc = cm._cmd_validate(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 1
    assert "corpus is empty" in captured.err


def test_cmd_validate_all_pass(corpus_root: Path, capsys) -> None:
    # Arrange
    cat = corpus_root / "demo"
    cat.mkdir()
    (cat / "clean.ts").write_text("ok", encoding="utf-8")
    (cat / "dirty.ts").write_text("bad", encoding="utf-8")
    args = MagicMock()
    args.fail_under = None

    def fake_run(path):
        return (0 if "clean" in path else 2, "")

    # Act
    with patch("corpus_manage._run_hook_on_file", side_effect=fake_run):
        rc = cm._cmd_validate(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "2/2 passed (100.0%)" in captured.out


def test_cmd_validate_with_failures(corpus_root: Path, capsys) -> None:
    # Arrange
    cat = corpus_root / "demo"
    cat.mkdir()
    (cat / "clean.ts").write_text("ok", encoding="utf-8")
    (cat / "dirty.ts").write_text("bad", encoding="utf-8")
    args = MagicMock()
    args.fail_under = None

    # Act
    with patch("corpus_manage._run_hook_on_file", return_value=(0, "")):
        rc = cm._cmd_validate(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 1
    assert "FAIL" in captured.out


def test_cmd_validate_fail_under_threshold(corpus_root: Path, capsys) -> None:
    # Arrange
    cat = corpus_root / "demo"
    cat.mkdir()
    (cat / "clean.ts").write_text("ok", encoding="utf-8")
    (cat / "dirty.ts").write_text("bad", encoding="utf-8")
    args = MagicMock()
    args.fail_under = 99.0

    # Act: half the corpus passes -> 50%
    with patch("corpus_manage._run_hook_on_file", return_value=(0, "")):
        rc = cm._cmd_validate(args)

    # Assert
    assert rc == 1


def test_cmd_validate_unknown_filename_fails(corpus_root: Path, capsys) -> None:
    # Arrange
    cat = corpus_root / "demo"
    cat.mkdir()
    (cat / "weird.ts").write_text("ok", encoding="utf-8")
    args = MagicMock()
    args.fail_under = None

    # Act
    rc = cm._cmd_validate(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 1
    assert "filename must start with" in captured.out


# --------------------------------------------------------------------------- #
# _cmd_regenerate
# --------------------------------------------------------------------------- #


def test_cmd_regenerate_missing_version_file(corpus_root: Path, capsys) -> None:
    # Arrange
    args = MagicMock()

    # Act
    rc = cm._cmd_regenerate(args)
    captured = capsys.readouterr()

    # Assert
    assert rc == 1
    assert "VERSION file not found" in captured.err


def test_cmd_regenerate_updates_last_regenerated(corpus_root: Path, capsys) -> None:
    # Arrange
    version = corpus_root / "VERSION"
    version.write_text(
        "schema: 1\nlast_regenerated: 1970-01-01\nnotes: original\n", encoding="utf-8"
    )
    args = MagicMock()

    # Act
    rc = cm._cmd_regenerate(args)

    # Assert
    assert rc == 0
    contents = version.read_text(encoding="utf-8")
    assert "last_regenerated:" in contents
    assert "1970-01-01" not in contents
    assert "schema: 1" in contents
    assert "notes: original" in contents


# --------------------------------------------------------------------------- #
# _run_hook_on_file
# --------------------------------------------------------------------------- #


def test_run_hook_on_file_invokes_subprocess(tmp_path: Path) -> None:
    # Arrange
    fixture = tmp_path / "x.ts"
    fixture.write_text("source", encoding="utf-8")
    fake_proc = MagicMock(returncode=0, stderr="")

    # Act
    with patch("corpus_manage.subprocess.run", return_value=fake_proc) as patched:
        rc, err = cm._run_hook_on_file(str(fixture))

    # Assert
    assert rc == 0
    assert err == ""
    payload = json.loads(patched.call_args.kwargs["input"])
    assert payload["tool_name"] == "Write"
    assert payload["tool_input"]["content"] == "source"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def test_main_dispatches_list_subcommand(corpus_root: Path, capsys) -> None:
    # Arrange / Act
    rc = cm.main(["list"])
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "(corpus empty)" in captured.out


def test_main_module_entry_runs_as_subprocess(tmp_path: Path) -> None:
    # Arrange
    script = SCRIPTS_DIR / "corpus_manage.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(script), "list"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    # Assert
    assert proc.returncode in (0, 1)

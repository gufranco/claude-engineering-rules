"""In-process tests for scripts/validate-markdown-links.py.

The subprocess-based tests in :mod:`test_validate_markdown_links` exercise
the validator's CLI surface but do not contribute to coverage because the
subprocess runs in a separate Python interpreter.

This module imports the validator module directly and drives its functions
to bring coverage on the validator to the project floor.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate-markdown-links.py"

# Load the module with a Python-safe name since the file has a hyphen.
spec = importlib.util.spec_from_file_location(
    "validate_markdown_links",
    VALIDATOR_PATH,
)
validate_module = importlib.util.module_from_spec(spec)
sys.modules["validate_markdown_links"] = validate_module
spec.loader.exec_module(validate_module)


def test_tracked_markdown_files_returns_list():
    result = validate_module.tracked_markdown_files(REPO_ROOT)
    assert isinstance(result, list)
    assert any(f.endswith(".md") for f in result)


def test_collect_findings_empty_for_no_files():
    bare, broken = validate_module.collect_findings([], REPO_ROOT)
    assert bare == []
    assert broken == []


def test_collect_findings_handles_missing_file():
    # Arrange: a path that does not exist
    bare, broken = validate_module.collect_findings(["does-not-exist.md"], REPO_ROOT)
    # Assert: silently skip missing files
    assert bare == []
    assert broken == []


def test_main_returns_zero_when_repo_clean(monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(sys, "argv", ["validate-markdown-links.py"])

    # Act
    code = validate_module.main()

    # Assert
    assert code == 0
    captured = capsys.readouterr()
    assert "PASSED" in captured.out


def test_main_accepts_absolute_path_outside_repo(monkeypatch, capsys, tmp_path):
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text("Plain text, no references.\n")
    monkeypatch.setattr(sys, "argv", ["validate-markdown-links.py", str(target)])

    # Act
    code = validate_module.main()

    # Assert
    assert code == 0
    captured = capsys.readouterr()
    assert "PASSED" in captured.out


def test_main_with_include_advisory_flag(monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(
        sys, "argv", ["validate-markdown-links.py", "--include-advisory"]
    )

    # Act
    code = validate_module.main()

    # Assert
    # Repo is clean, advisory or otherwise.
    assert code == 0
    captured = capsys.readouterr()
    assert "PASSED" in captured.out


def test_main_reports_findings_for_bare_reference(monkeypatch, capsys, tmp_path):
    # Arrange
    target = REPO_ROOT / "tmp-validator-inprocess.md"
    target.write_text("Look at `README.md` here.\n")
    try:
        monkeypatch.setattr(sys, "argv", ["validate-markdown-links.py", str(target)])
        # Act
        code = validate_module.main()
        # Assert
        assert code == 1
        captured = capsys.readouterr()
        assert "FAILED" in captured.out
        assert "README.md" in captured.out
    finally:
        target.unlink(missing_ok=True)


def test_main_reports_broken_link_target(monkeypatch, capsys, tmp_path):
    # Arrange: link target does not exist
    target = REPO_ROOT / "tmp-validator-broken-link.md"
    target.write_text("See [missing](ghost-file.md).\n")
    try:
        monkeypatch.setattr(sys, "argv", ["validate-markdown-links.py", str(target)])
        # Act
        code = validate_module.main()
        # Assert
        assert code == 1
        captured = capsys.readouterr()
        assert "FAILED" in captured.out
        assert "broken link target" in captured.out
        assert "ghost-file.md" in captured.out
    finally:
        target.unlink(missing_ok=True)


def test_main_reports_advisory_bare_findings_in_specs(monkeypatch, capsys):
    # Arrange: bare reference in specs/ is advisory, not blocking
    spec_target = REPO_ROOT / "specs" / "tmp-validator-advisory-bare.md"
    spec_target.parent.mkdir(parents=True, exist_ok=True)
    spec_target.write_text("Look at `README.md` here.\n")
    try:
        monkeypatch.setattr(
            sys, "argv", ["validate-markdown-links.py", str(spec_target)]
        )
        # Act
        code = validate_module.main()
        # Assert: passes (advisory only) but reports the advisory finding
        assert code == 0
        captured = capsys.readouterr()
        assert "Advisory" in captured.out
        assert "bare file reference" in captured.out
    finally:
        spec_target.unlink(missing_ok=True)


def test_main_reports_advisory_broken_targets_in_specs(monkeypatch, capsys):
    # Arrange: broken link target in specs/ is advisory
    spec_target = REPO_ROOT / "specs" / "tmp-validator-advisory-broken.md"
    spec_target.parent.mkdir(parents=True, exist_ok=True)
    spec_target.write_text("See [missing](ghost.md).\n")
    try:
        monkeypatch.setattr(
            sys, "argv", ["validate-markdown-links.py", str(spec_target)]
        )
        # Act
        code = validate_module.main()
        # Assert
        assert code == 0
        captured = capsys.readouterr()
        assert "Advisory" in captured.out
        assert "broken link target" in captured.out
    finally:
        spec_target.unlink(missing_ok=True)

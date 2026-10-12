from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".github" / "scripts" / "validate-markdown-links.py"

spec = importlib.util.spec_from_file_location(
    "validate_markdown_links",
    VALIDATOR_PATH,
)
validate_module = importlib.util.module_from_spec(spec)
sys.modules["validate_markdown_links"] = validate_module
spec.loader.exec_module(validate_module)


def test_tracked_markdown_files_returns_list():
    # Arrange
    root = REPO_ROOT

    # Act
    result = validate_module.tracked_markdown_files(root)

    # Assert
    assert isinstance(result, list) is True
    assert "README.md" in result


def test_collect_findings_empty_for_no_files():
    # Arrange
    files = []

    # Act
    bare, broken = validate_module.collect_findings(files, REPO_ROOT)

    # Assert
    assert bare == []
    assert broken == []


def test_collect_findings_handles_missing_file():
    # Arrange
    files = ["does-not-exist.md"]

    # Act
    bare, broken = validate_module.collect_findings(files, REPO_ROOT)

    # Assert
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
    assert code == 0
    captured = capsys.readouterr()
    assert "PASSED" in captured.out


def test_main_reports_findings_for_bare_reference(monkeypatch, capsys, repo_scratch):
    # Arrange
    target = repo_scratch("tmp-validator-inprocess.md", "Look at `README.md` here.\n")
    monkeypatch.setattr(sys, "argv", ["validate-markdown-links.py", str(target)])

    # Act
    code = validate_module.main()

    # Assert
    captured = capsys.readouterr()
    assert code == 1
    assert "FAILED" in captured.out
    assert "README.md" in captured.out


def test_main_reports_broken_link_target(monkeypatch, capsys, repo_scratch):
    # Arrange
    target = repo_scratch(
        "tmp-validator-broken-link.md", "See [missing](ghost-file.md).\n"
    )
    monkeypatch.setattr(sys, "argv", ["validate-markdown-links.py", str(target)])

    # Act
    code = validate_module.main()

    # Assert
    captured = capsys.readouterr()
    assert code == 1
    assert "FAILED" in captured.out
    assert "broken link target" in captured.out
    assert "ghost-file.md" in captured.out


def test_main_reports_advisory_bare_findings_in_specs(
    monkeypatch, capsys, repo_scratch
):
    # Arrange
    spec_target = repo_scratch(
        "specs/tmp-validator-advisory-bare.md", "Look at `README.md` here.\n"
    )
    monkeypatch.setattr(sys, "argv", ["validate-markdown-links.py", str(spec_target)])

    # Act
    code = validate_module.main()

    # Assert
    captured = capsys.readouterr()
    assert code == 0
    assert "Advisory" in captured.out
    assert "bare file reference" in captured.out


def test_main_reports_advisory_broken_targets_in_specs(
    monkeypatch, capsys, repo_scratch
):
    # Arrange
    spec_target = repo_scratch(
        "specs/tmp-validator-advisory-broken.md", "See [missing](ghost.md).\n"
    )
    monkeypatch.setattr(sys, "argv", ["validate-markdown-links.py", str(spec_target)])

    # Act
    code = validate_module.main()

    # Assert
    captured = capsys.readouterr()
    assert code == 0
    assert "Advisory" in captured.out
    assert "broken link target" in captured.out

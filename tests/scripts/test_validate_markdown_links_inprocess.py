from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".github" / "scripts" / "validate-markdown-links.py"
SCRIPT_NAME = "validate-markdown-links.py"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_markdown_links", VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_markdown_links"] = module
    spec.loader.exec_module(module)
    return module


validate_module = _load_validator()


def _point_validator_at(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(validate_module, "REPO_ROOT", root)


def test_tracked_markdown_files_lists_only_tracked_markdown(
    scratch_repo_root: Path,
) -> None:
    # Arrange
    (scratch_repo_root / "untracked.md").write_text("# Untracked\n", encoding="utf-8")

    # Act
    result = validate_module.tracked_markdown_files(scratch_repo_root)

    # Assert
    assert result == ["README.md"]


def test_collect_findings_empty_for_no_files() -> None:
    # Arrange
    files: list[str] = []

    # Act
    bare, broken = validate_module.collect_findings(files, REPO_ROOT)

    # Assert
    assert (bare, broken) == ([], [])


def test_collect_findings_fails_on_a_missing_file(faker: Faker) -> None:
    # Arrange
    missing = f"{faker.uuid4()}.md"

    # Act
    with pytest.raises(SystemExit) as exit_info:
        validate_module.collect_findings([missing], REPO_ROOT)

    # Assert
    assert str(exit_info.value.code).startswith(f"FAILED: cannot read {missing}: ")


def test_main_returns_zero_when_repo_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "argv", [SCRIPT_NAME])

    # Act
    code = validate_module.main()

    # Assert
    assert code == 0
    assert capsys.readouterr().out.startswith("PASSED: 0 blocking findings across ")


def test_main_accepts_absolute_path_outside_repo(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    faker: Faker,
) -> None:
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text(f"{faker.sentence()}\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [SCRIPT_NAME, str(target)])

    # Act
    code = validate_module.main()

    # Assert
    assert code == 0
    assert capsys.readouterr().out == (
        "PASSED: 0 blocking findings across 1 markdown files "
        "(bare references + broken link targets).\n"
    )


def test_main_with_include_advisory_flag_passes_a_clean_tree(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    scratch_repo_root: Path,
) -> None:
    # Arrange
    _point_validator_at(monkeypatch, scratch_repo_root)
    monkeypatch.setattr(sys, "argv", [SCRIPT_NAME, "--include-advisory"])

    # Act
    code = validate_module.main()

    # Assert
    assert code == 0
    assert capsys.readouterr().out == (
        "PASSED: 0 blocking findings across 1 markdown files "
        "(bare references + broken link targets).\n"
    )


def test_main_reports_findings_for_bare_reference(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    repo_scratch: Callable[[str, str], Path],
    scratch_repo_root: Path,
) -> None:
    # Arrange
    target = repo_scratch("bare.md", "Look at `README.md` here.\n")
    _point_validator_at(monkeypatch, scratch_repo_root)
    monkeypatch.setattr(sys, "argv", [SCRIPT_NAME, str(target)])

    # Act
    code = validate_module.main()

    # Assert
    out = capsys.readouterr().out
    assert code == 1
    assert out.startswith("FAILED: 1 bare file reference(s) found\n")
    assert "bare.md:1:9: `README.md` -> existing file at README.md, not linked" in out


def test_main_reports_broken_link_target(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    repo_scratch: Callable[[str, str], Path],
    scratch_repo_root: Path,
) -> None:
    # Arrange
    target = repo_scratch("broken.md", "See [missing](ghost-file.md).\n")
    _point_validator_at(monkeypatch, scratch_repo_root)
    monkeypatch.setattr(sys, "argv", [SCRIPT_NAME, str(target)])

    # Act
    code = validate_module.main()

    # Assert
    out = capsys.readouterr().out
    assert code == 1
    assert out.startswith("FAILED: 1 broken link target(s) found\n")
    assert "broken.md:1:15: [missing](ghost-file.md)" in out


def test_main_reports_advisory_bare_findings_in_specs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    repo_scratch: Callable[[str, str], Path],
    scratch_repo_root: Path,
) -> None:
    # Arrange
    target = repo_scratch("specs/advisory-bare.md", "Look at `README.md` here.\n")
    _point_validator_at(monkeypatch, scratch_repo_root)
    monkeypatch.setattr(sys, "argv", [SCRIPT_NAME, str(target)])

    # Act
    code = validate_module.main()

    # Assert
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("Advisory: 1 bare file reference(s) in specs/\n")


def test_main_reports_advisory_broken_targets_in_specs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    repo_scratch: Callable[[str, str], Path],
    scratch_repo_root: Path,
) -> None:
    # Arrange
    target = repo_scratch("specs/advisory-broken.md", "See [missing](ghost.md).\n")
    _point_validator_at(monkeypatch, scratch_repo_root)
    monkeypatch.setattr(sys, "argv", [SCRIPT_NAME, str(target)])

    # Act
    code = validate_module.main()

    # Assert
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("Advisory: 1 broken link target(s) in specs/\n")

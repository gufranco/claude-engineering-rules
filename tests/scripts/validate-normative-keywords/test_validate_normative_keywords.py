from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "validate-normative-keywords.py"


@pytest.fixture(scope="module")
def validator_mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_normative_keywords", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["validate_normative_keywords"] = mod
    spec.loader.exec_module(mod)
    return mod


def _rule_file(tmp_path: Path, faker: Faker, text: str) -> Path:
    path = tmp_path / f"{faker.word()}.md"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("keyword", ["Should", "should"])
def test_scan_detects_should_bullet(
    validator_mod: ModuleType, tmp_path: Path, faker: Faker, keyword: str
) -> None:
    # Arrange
    line = f"- {keyword} {faker.word()} {faker.word()}."
    f = _rule_file(tmp_path, faker, f"{line}\n")

    # Act
    findings = validator_mod.scan(f, "rules/rule.md")

    # Assert
    assert findings == [(1, "should-bullet", line)]


@pytest.mark.parametrize(
    ("phrase", "category"),
    [
        ("Great question!", "banned-opener"),
        ("Hope this helps", "banned-closer"),
        ("It's worth noting", "banned-hedge"),
        ("That said,", "banned-transition"),
    ],
)
def test_scan_detects_banned_phrase(
    validator_mod: ModuleType,
    tmp_path: Path,
    faker: Faker,
    phrase: str,
    category: str,
) -> None:
    # Arrange
    line = f"{phrase} {faker.word()} {faker.word()}."
    f = _rule_file(tmp_path, faker, f"{line}\n")

    # Act
    findings = validator_mod.scan(f, "rules/rule.md")

    # Assert
    assert findings == [(1, category, line)]


def test_scan_skips_code_fences(
    validator_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    f = _rule_file(
        tmp_path,
        faker,
        f"{faker.word()}.\n```\n- Should {faker.word()}.\nGreat question!\n```\n",
    )

    # Act
    findings = validator_mod.scan(f, "rules/rule.md")

    # Assert
    assert findings == []


def test_scan_skips_banned_phrases_in_self_reference_files(
    validator_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    f = _rule_file(tmp_path, faker, "Banned: Great question! Hope this helps.\n")

    # Act
    findings = validator_mod.scan(f, "rules/writing-precision.md")

    # Assert
    assert findings == []


def test_scan_still_flags_should_bullets_in_self_reference_files(
    validator_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    line = f"- Should {faker.word()}."
    f = _rule_file(tmp_path, faker, f"{line}\n")

    # Act
    findings = validator_mod.scan(f, "rules/writing-precision.md")

    # Assert
    assert findings == [(1, "should-bullet", line)]


def test_scan_clean_file_produces_no_findings(
    validator_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    f = _rule_file(tmp_path, faker, f"- Must {faker.word()}.\n- May {faker.word()}.\n")

    # Act
    findings = validator_mod.scan(f, "rules/clean.md")

    # Assert
    assert findings == []


def test_scan_reports_an_unreadable_file(
    validator_mod: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    f = tmp_path / "bad.md"
    f.write_bytes(b"\xff\xfe\xfd")

    # Act
    findings = validator_mod.scan(f, "rules/bad.md")

    # Assert
    assert [finding[:2] for finding in findings] == [(0, "unreadable")]


def test_walk_in_scope_includes_in_scope_dirs(
    validator_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    for directory, name in [
        ("rules", "a.md"),
        ("standards", "b.md"),
        ("checklists", "c.md"),
        ("specs", "e.md"),
    ]:
        (tmp_path / directory).mkdir()
        (tmp_path / directory / name).write_text(faker.word())
    (tmp_path / "CLAUDE.md").write_text(faker.word())

    # Act
    files = list(validator_mod.walk_in_scope(tmp_path))

    # Assert
    assert {p.name for p in files} == {"a.md", "b.md", "c.md", "CLAUDE.md"}


def test_walk_in_scope_handles_missing_dirs(
    validator_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "a.md").write_text(faker.word())

    # Act
    files = list(validator_mod.walk_in_scope(tmp_path))

    # Assert
    assert files == [tmp_path / "rules" / "a.md"]


def test_walk_in_scope_skips_dotfiles(
    validator_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / ".hidden").mkdir()
    (tmp_path / "rules" / ".hidden" / "x.md").write_text(faker.word())
    (tmp_path / "rules" / "ok.md").write_text(faker.word())

    # Act
    files = list(validator_mod.walk_in_scope(tmp_path))

    # Assert
    assert {p.name for p in files} == {"ok.md"}


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("rules/normative-keywords.md", True),
        ("rules/writing-precision.md", True),
        ("CLAUDE.md", True),
        ("rules/random.md", False),
    ],
)
def test_is_self_reference_recognizes_known_paths(
    validator_mod: ModuleType, path: str, expected: bool
) -> None:
    # Arrange
    candidate = path

    # Act
    result = validator_mod.is_self_reference(candidate)

    # Assert
    assert result is expected


def test_main_clean_exits_zero(
    validator_mod: ModuleType,
    tmp_path: Path,
    faker: Faker,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "ok.md").write_text(f"- Must {faker.word()}.\n")
    monkeypatch.setattr(
        "sys.argv",
        ["validate-normative-keywords.py", "--root", str(tmp_path)],
    )

    # Act
    code = validator_mod.main()

    # Assert
    assert code == 0
    assert capsys.readouterr().out == (
        "Clean: no normative-keyword or banned-phrase findings.\n"
    )


def test_main_dirty_exits_one(
    validator_mod: ModuleType,
    tmp_path: Path,
    faker: Faker,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    line = f"- Should {faker.word()}."
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "bad.md").write_text(f"{line}\n")
    monkeypatch.setattr(
        "sys.argv",
        ["validate-normative-keywords.py", "--root", str(tmp_path)],
    )

    # Act
    code = validator_mod.main()

    # Assert
    assert code == 1
    assert capsys.readouterr().out == (
        "rules/bad.md: 1 finding(s)\n"
        f"     1  [should-bullet]  {line}\n"
        "\nTotal: 1 finding(s).\n"
    )

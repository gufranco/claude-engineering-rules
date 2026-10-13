from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "validate-clarity.py"


@pytest.fixture(scope="module")
def clarity_mod():
    spec = importlib.util.spec_from_file_location("validate_clarity", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["validate_clarity"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_pronoun_it_flagged_with_multi_noun_prev(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "rule.md"
    f.write_text(
        "- The schema validates the input before the writer commits.\n"
        "- It must catch invalid data.\n"
    )

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert any(c == "pronoun-leading" for _, c, _ in findings)


def test_pronoun_this_flagged(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "rule.md"
    f.write_text(
        "- The handler reads the queue and emits an event.\n"
        "- This must succeed every time.\n"
    )

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert any(c == "pronoun-leading" for _, c, _ in findings)


def test_pronoun_unflagged_when_no_prev_nouns(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "rule.md"
    f.write_text("- It validates input.\n")

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert all(c != "pronoun-leading" for _, c, _ in findings)


def test_pronoun_unflagged_when_prev_is_short(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "rule.md"
    f.write_text("- ok.\n- It must run.\n")

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert all(c != "pronoun-leading" for _, c, _ in findings)


def test_passive_bullet_flagged(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "rule.md"
    f.write_text("- The input is validated before processing.\n")

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert any(c == "passive-bullet" for _, c, _ in findings)


def test_passive_with_actor_hint_not_flagged(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "rule.md"
    f.write_text("- The input is validated by the handler before processing.\n")

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert all(c != "passive-bullet" for _, c, _ in findings)


def test_active_voice_not_flagged(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "rule.md"
    f.write_text("- The handler validates the input before processing.\n")

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert all(c != "passive-bullet" for _, c, _ in findings)


def test_irregular_participle_detected(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "rule.md"
    f.write_text("- The record is set during init.\n")

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert any(c == "passive-bullet" for _, c, _ in findings)


def test_skips_code_fences(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "rule.md"
    f.write_text(
        "Real prose.\n"
        "```python\n"
        "- It is validated by the parser.\n"
        "- The form is processed.\n"
        "```\n"
    )

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert findings == []


def test_walk_includes_in_scope_dirs(clarity_mod, tmp_path):
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "a.md").write_text("a")
    (tmp_path / "standards").mkdir()
    (tmp_path / "standards" / "b.md").write_text("b")
    (tmp_path / "checklists").mkdir()
    (tmp_path / "checklists" / "c.md").write_text("c")
    (tmp_path / "CLAUDE.md").write_text("d")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "e.md").write_text("e")

    # Act
    files = list(clarity_mod.walk_in_scope(tmp_path))

    # Assert
    names = {p.name for p in files}
    assert names == {"a.md", "b.md", "c.md", "CLAUDE.md"}


def test_walk_skips_dotdirs(clarity_mod, tmp_path):
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / ".hidden").mkdir()
    (tmp_path / "rules" / ".hidden" / "x.md").write_text("x")
    (tmp_path / "rules" / "ok.md").write_text("ok")

    # Act
    files = list(clarity_mod.walk_in_scope(tmp_path))

    # Assert
    assert {p.name for p in files} == {"ok.md"}


def test_walk_handles_missing_dirs(clarity_mod, tmp_path):
    # Arrange
    root = tmp_path

    # Act
    files = list(clarity_mod.walk_in_scope(root))

    # Assert
    assert files == []


def test_scan_reports_an_unreadable_file(clarity_mod, tmp_path):
    # Arrange
    f = tmp_path / "bad.md"
    f.write_bytes(b"\xff\xfe\xfd")

    # Act
    findings = clarity_mod.scan(f)

    # Assert
    assert [finding[:2] for finding in findings] == [(0, "unreadable")]


@pytest.mark.parametrize("line", ["", "   "])
def test_has_multiple_nouns_empty_line(clarity_mod, line):
    # Arrange
    text = line

    # Act
    result = clarity_mod._has_multiple_nouns(text)

    # Assert
    assert result is False


def test_has_multiple_nouns_short_words_ignored(clarity_mod):
    # Arrange
    prev_line = "a b c"

    # Act
    result = clarity_mod._has_multiple_nouns(prev_line)

    # Assert
    assert result is False


@pytest.mark.parametrize(
    ("line", "expected"),
    [("validator validator", False), ("validator handler", True)],
)
def test_has_multiple_nouns_counts_distinct(clarity_mod, line, expected):
    # Arrange
    text = line

    # Act
    result = clarity_mod._has_multiple_nouns(text)

    # Assert
    assert result is expected


def test_main_clean_exits_zero(clarity_mod, tmp_path, monkeypatch, capsys):
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "ok.md").write_text("- The handler validates input.\n")
    monkeypatch.setattr(
        "sys.argv",
        ["validate-clarity.py", "--root", str(tmp_path)],
    )

    # Act
    code = clarity_mod.main()

    # Assert
    out = capsys.readouterr().out
    assert code == 0
    assert "Clean" in out


def test_main_with_findings_still_exits_zero(
    clarity_mod, tmp_path, monkeypatch, capsys
):
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "bad.md").write_text(
        "- The input is validated before processing.\n"
    )
    monkeypatch.setattr(
        "sys.argv",
        ["validate-clarity.py", "--root", str(tmp_path)],
    )

    # Act
    code = clarity_mod.main()

    # Assert
    out = capsys.readouterr().out
    assert code == 0
    assert "passive-bullet" in out
    assert "Total" in out

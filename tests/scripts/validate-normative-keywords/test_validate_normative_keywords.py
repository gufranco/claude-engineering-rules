"""Coverage for scripts/validate-normative-keywords.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate-normative-keywords.py"


@pytest.fixture(scope="module")
def validator_mod():
    import sys

    spec = importlib.util.spec_from_file_location(
        "validate_normative_keywords", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["validate_normative_keywords"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------- scan ----------


def test_scan_detects_should_bullet(validator_mod, tmp_path):
    f = tmp_path / "rule.md"
    f.write_text("- Should validate input.\n")
    findings = validator_mod.scan(f, "rules/rule.md")
    assert any(c == "should-bullet" for _, c, _ in findings)


def test_scan_detects_lowercase_should_bullet(validator_mod, tmp_path):
    f = tmp_path / "rule.md"
    f.write_text("- should validate input.\n")
    findings = validator_mod.scan(f, "rules/rule.md")
    assert any(c == "should-bullet" for _, c, _ in findings)


def test_scan_detects_opener(validator_mod, tmp_path):
    f = tmp_path / "rule.md"
    f.write_text("Great question! Here is the answer.\n")
    findings = validator_mod.scan(f, "rules/rule.md")
    assert any(c == "banned-opener" for _, c, _ in findings)


def test_scan_detects_closer(validator_mod, tmp_path):
    f = tmp_path / "rule.md"
    f.write_text("Hope this helps your team.\n")
    findings = validator_mod.scan(f, "rules/rule.md")
    assert any(c == "banned-closer" for _, c, _ in findings)


def test_scan_detects_hedge(validator_mod, tmp_path):
    f = tmp_path / "rule.md"
    f.write_text("It's worth noting that the API changed.\n")
    findings = validator_mod.scan(f, "rules/rule.md")
    assert any(c == "banned-hedge" for _, c, _ in findings)


def test_scan_detects_transition(validator_mod, tmp_path):
    f = tmp_path / "rule.md"
    f.write_text("That said, this is the correct way.\n")
    findings = validator_mod.scan(f, "rules/rule.md")
    assert any(c == "banned-transition" for _, c, _ in findings)


def test_scan_skips_code_fences(validator_mod, tmp_path):
    f = tmp_path / "rule.md"
    f.write_text("Real prose.\n```\n- Should validate input.\nGreat question!\n```\n")
    findings = validator_mod.scan(f, "rules/rule.md")
    assert findings == []


def test_scan_skips_self_reference_phrases(validator_mod, tmp_path):
    f = tmp_path / "writing-precision.md"
    f.write_text("Banned: Great question! Hope this helps.\n")
    findings = validator_mod.scan(f, "rules/writing-precision.md")
    # Banned phrases skipped, but should-bullet still applies.
    assert all(c == "should-bullet" for _, c, _ in findings)


def test_scan_clean_file_produces_no_findings(validator_mod, tmp_path):
    f = tmp_path / "clean.md"
    f.write_text("- Must validate input.\n- May skip null values.\n")
    findings = validator_mod.scan(f, "rules/clean.md")
    assert findings == []


def test_scan_handles_unreadable(validator_mod, tmp_path):
    f = tmp_path / "bad.md"
    f.write_bytes(b"\xff\xfe\xfd")
    findings = validator_mod.scan(f, "rules/bad.md")
    assert findings == []


# ---------- walk_in_scope ----------


def test_walk_in_scope_includes_in_scope_dirs(validator_mod, tmp_path):
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "a.md").write_text("a")
    (tmp_path / "standards").mkdir()
    (tmp_path / "standards" / "b.md").write_text("b")
    (tmp_path / "checklists").mkdir()
    (tmp_path / "checklists" / "c.md").write_text("c")
    (tmp_path / "CLAUDE.md").write_text("d")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "e.md").write_text("e")
    files = list(validator_mod.walk_in_scope(tmp_path))
    names = {p.name for p in files}
    assert names == {"a.md", "b.md", "c.md", "CLAUDE.md"}


def test_walk_in_scope_handles_missing_dirs(validator_mod, tmp_path):
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "a.md").write_text("a")
    files = list(validator_mod.walk_in_scope(tmp_path))
    assert any(p.name == "a.md" for p in files)


def test_walk_in_scope_skips_dotfiles(validator_mod, tmp_path):
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / ".hidden").mkdir()
    (tmp_path / "rules" / ".hidden" / "x.md").write_text("x")
    (tmp_path / "rules" / "ok.md").write_text("ok")
    files = list(validator_mod.walk_in_scope(tmp_path))
    names = {p.name for p in files}
    assert names == {"ok.md"}


# ---------- is_self_reference ----------


def test_is_self_reference_recognizes_known_paths(validator_mod):
    assert validator_mod.is_self_reference("rules/normative-keywords.md")
    assert validator_mod.is_self_reference("rules/writing-precision.md")
    assert validator_mod.is_self_reference("CLAUDE.md")
    assert not validator_mod.is_self_reference("rules/random.md")


# ---------- main ----------


def test_main_clean_exits_zero(validator_mod, tmp_path, monkeypatch, capsys):
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "ok.md").write_text("- Must validate input.\n")
    monkeypatch.setattr(
        "sys.argv",
        ["validate-normative-keywords.py", "--root", str(tmp_path)],
    )
    code = validator_mod.main()
    out = capsys.readouterr().out
    assert code == 0
    assert "Clean" in out


def test_main_dirty_exits_one(validator_mod, tmp_path, monkeypatch, capsys):
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "bad.md").write_text("- Should validate input.\n")
    monkeypatch.setattr(
        "sys.argv",
        ["validate-normative-keywords.py", "--root", str(tmp_path)],
    )
    code = validator_mod.main()
    out = capsys.readouterr().out
    assert code == 1
    assert "should-bullet" in out
    assert "Total" in out

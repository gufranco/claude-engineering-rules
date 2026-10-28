from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker


def _two_findings(audit_mod: ModuleType, faker: Faker) -> list[object]:
    return [
        audit_mod.Finding("doc.md", 1, "banned-em-dash", "U+2014", faker.word()),
        audit_mod.Finding("doc.md", 2, "should-bullet", faker.word(), faker.word()),
    ]


def test_write_jsonl_writes_one_object_per_finding(
    audit_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    findings = _two_findings(audit_mod, faker)
    jsonl = tmp_path / "out.jsonl"

    # Act
    audit_mod.write_jsonl(findings, jsonl)

    # Assert
    assert [json.loads(line) for line in jsonl.read_text().splitlines()] == [
        {
            "file": f.file,
            "line": f.line,
            "category": f.category,
            "detail": f.detail,
            "snippet": f.snippet,
        }
        for f in findings
    ]


def _expected_markdown(
    first_snippet: str, second_detail: str, second_snippet: str
) -> str:
    return "\n".join(
        [
            "# Audit Findings",
            "",
            "Total: 2 findings across 1 files.",
            "",
            "## Summary by Category",
            "",
            "| Category | Count |",
            "|----------|-------|",
            "| banned-em-dash | 1 |",
            "| should-bullet | 1 |",
            "",
            "## Per-File Findings",
            "",
            "### doc.md",
            "",
            "2 findings.",
            "",
            "| Line | Category | Detail | Snippet |",
            "|------|----------|--------|---------|",
            f"| 1 | banned-em-dash | U+2014 | {first_snippet} |",
            f"| 2 | should-bullet | {second_detail} | {second_snippet} |",
            "",
        ]
    )


def test_write_markdown_renders_summary_and_rows(
    audit_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    findings = _two_findings(audit_mod, faker)
    md = tmp_path / "out.md"
    first, second = findings

    # Act
    audit_mod.write_markdown(findings, md)

    # Assert
    assert md.read_text() == _expected_markdown(
        first.snippet, second.detail, second.snippet
    )


def test_write_markdown_pipe_escape(
    audit_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    category = faker.word()
    findings = [
        audit_mod.Finding("doc.md", 1, category, "with | pipe", "a | b"),
    ]
    md = tmp_path / "out.md"

    # Act
    audit_mod.write_markdown(findings, md)

    # Assert
    assert md.read_text().splitlines()[-1] == (
        f"| 1 | {category} | with \\| pipe | a \\| b |"
    )


def _set_main_argv(monkeypatch: pytest.MonkeyPatch, root: Path, out_dir: Path) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "audit-writing-quality.py",
            "--root",
            str(root),
            "--out-dir",
            str(out_dir),
        ],
    )


def test_main_writes_outputs(
    audit_mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "doc.md").write_text("- Should validate input.\n")
    out_dir = tmp_path / "out"
    _set_main_argv(monkeypatch, tmp_path, out_dir)

    # Act
    code = audit_mod.main()

    # Assert
    assert code == 0
    assert [
        json.loads(line)["category"]
        for line in (out_dir / "audit-findings.jsonl").read_text().splitlines()
    ] == ["should-bullet"]
    assert (out_dir / "audit-findings.md").read_text().splitlines()[2] == (
        "Total: 1 findings across 1 files."
    )


def test_main_handles_unreadable_file(
    audit_mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    (tmp_path / "rules").mkdir()
    bad = tmp_path / "rules" / "bad.md"
    bad.write_bytes(b"\xff\xfe\xfd")
    out_dir = tmp_path / "out"
    _set_main_argv(monkeypatch, tmp_path, out_dir)

    # Act
    code = audit_mod.main()

    # Assert
    assert code == 0
    assert [
        (record["file"], record["line"], record["category"])
        for record in map(
            json.loads,
            (out_dir / "audit-findings.jsonl").read_text().splitlines(),
        )
    ] == [("rules/bad.md", 0, "unreadable")]


def test_snippet_truncates(audit_mod: ModuleType, faker: Faker) -> None:
    # Arrange
    long = faker.pystr(min_chars=200, max_chars=200)

    # Act
    snippet = audit_mod.snippet_of(long, length=50)

    # Assert
    assert snippet == long[:50] + "..."


def test_snippet_keeps_short_text_whole(audit_mod: ModuleType, faker: Faker) -> None:
    # Arrange
    short = faker.pystr(min_chars=10, max_chars=10)

    # Act
    snippet = audit_mod.snippet_of(short)

    # Assert
    assert snippet == short


def test_a_relative_out_dir_lands_under_the_root(
    audit_mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "doc.md").write_text("# Doc\n")
    _set_main_argv(monkeypatch, tmp_path, Path("reports"))

    # Act
    code = audit_mod.main()

    # Assert
    assert code == 0
    assert (tmp_path / "reports" / "audit-findings.md").is_file()


def test_the_script_runs_as_a_program(tmp_path: Path) -> None:
    # Arrange
    import os
    import subprocess
    import sys

    from _helpers.cov_env import apply_coverage_env

    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "doc.md").write_text("# Doc\n")
    script = Path(audit_mod_path())

    # Act
    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(tmp_path), "--out-dir", "out"],
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=60,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    assert proc.stderr.startswith("Wrote 0 findings to ")


def audit_mod_path() -> str:
    return str(
        Path(__file__).resolve().parents[3]
        / ".github"
        / "scripts"
        / "audit-writing-quality.py"
    )


def test_frontmatter_and_inline_code_are_not_scanned(audit_mod: ModuleType) -> None:
    # Arrange
    text = "---\ntitle: Should we\n---\n- **Openers**: Great question\nUse `foo (bar)` here.\n"

    # Act
    findings = audit_mod.scan_text("rules/doc.md", text)

    # Assert
    assert findings == []


def test_mask_code_regions_blanks_inline_code(audit_mod: ModuleType) -> None:
    # Arrange
    text = "see `code` here\n"

    # Act
    result = audit_mod._mask_code_regions(text)

    # Assert
    assert result == "see        here\n"

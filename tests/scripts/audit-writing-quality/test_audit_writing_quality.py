from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "audit-writing-quality.py"


@pytest.fixture(scope="module")
def audit_mod():
    import sys

    spec = importlib.util.spec_from_file_location("audit_writing_quality", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audit_writing_quality"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_em_dash_detected(audit_mod):
    # Arrange
    text = "Plain prose with " + chr(0x2014) + " in it."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "banned-em-dash" for f in findings)


def test_box_drawing_detected(audit_mod):
    # Arrange
    text = "ASCII art line " + chr(0x2500) + chr(0x2500) + " is bad."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "banned-box-drawing" for f in findings)


def test_emoji_detected(audit_mod):
    # Arrange
    text = "Decorative emoji " + chr(0x1F300) + " in prose."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "banned-emoji" for f in findings)


def test_should_bullet_detected(audit_mod):
    # Arrange
    text = "- Should validate input."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "should-bullet" for f in findings)


def test_banned_phrases_detected(audit_mod):
    # Arrange
    text = "Great question! Here is the answer."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "banned-opener" for f in findings)


def test_banned_fluff_detected(audit_mod):
    # Arrange
    text = "We need a robust solution."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "banned-fluff" for f in findings)


def test_banned_tactical_detected(audit_mod):
    # Arrange
    text = "Apply a quick fix and move on."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "banned-tactical" for f in findings)


def test_vague_quantifier_detected(audit_mod):
    # Arrange
    text = "- often the cause of flaky tests is shared state"

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "vague-quantifier" for f in findings)


def test_vague_quantifier_in_prose_not_flagged(audit_mod):
    # Arrange
    text = "Tests are often flaky on Mondays."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert all(f.category != "vague-quantifier" for f in findings)


def test_parens_in_prose_detected(audit_mod):
    # Arrange
    text = "This is a parenthetical (clause) in prose."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "parens-in-prose" for f in findings)


def test_code_fence_suppresses_detection(audit_mod):
    # Arrange
    text = "\n".join(
        [
            "Regular line.",
            "```python",
            "# Should validate input.",
            "x = (1 + 2)",
            "```",
            "Regular line again.",
        ]
    )

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert all(f.line not in (3, 4) for f in findings)


def test_inline_code_suppresses_detection(audit_mod):
    # Arrange
    text = "Use the `should()` helper to assert."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert all(f.category != "should-bullet" for f in findings)


def test_table_row_skips_parens_check(audit_mod):
    # Arrange
    text = "| col1 (a) | col2 (b) |"

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert all(f.category != "parens-in-prose" for f in findings)


def test_heading_skips_parens_check(audit_mod):
    # Arrange
    text = "## Title (subtitle)"

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert all(f.category != "parens-in-prose" for f in findings)


def test_link_text_with_parens_does_not_trigger(audit_mod):
    # Arrange
    text = "See [the doc](path/to/doc.md) for details."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert all(f.category != "parens-in-prose" for f in findings)


def test_empty_parens_skipped(audit_mod):
    # Arrange
    text = "Function call myFunction() in prose."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert all(f.category != "parens-in-prose" for f in findings)


@pytest.mark.parametrize(
    "text",
    [
        "Use `GAN_EVAL_MODE` (default `playwright`) for visual checks.",
        "Set the limit (default 50) before deployment.",
        "Pass the header (default: application/json) on every request.",
    ],
)
def test_default_carveout(audit_mod, text):
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert all(f.category != "parens-in-prose" for f in findings)


@pytest.mark.parametrize(
    "text",
    [
        "The full URL (REQUIRED) must include the scheme.",
        "The retry header (OPTIONAL) overrides the default.",
        "Use UUID v7 (RECOMMENDED) for new tables.",
        "Use UUID v7 (RECOMMENDED DEFAULT) for new tables.",
    ],
)
def test_emphasis_label_carveout(audit_mod, text):
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert all(f.category != "parens-in-prose" for f in findings)


@pytest.mark.parametrize(
    "text",
    [
        "Validate at boundaries (e.g., HTTP handlers and queue consumers).",
        "Validate at boundaries (e.g. HTTP handlers).",
        "Choose a parser (i.e., Zod or Valibot) for runtime validation.",
        "Choose a parser (i.e. Zod) for runtime validation.",
    ],
)
def test_eg_ie_carveout(audit_mod, text):
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert all(f.category != "parens-in-prose" for f in findings)


@pytest.mark.parametrize(
    "text",
    [
        "Apply the test rule (see testing.md) for every commit.",
        "Use Zod (per code-style.md) at boundaries.",
    ],
)
def test_see_per_carveout(audit_mod, text):
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert all(f.category != "parens-in-prose" for f in findings)


@pytest.mark.parametrize(
    "text",
    [
        "The handler (which also runs on websockets) validates the input.",
        "the cache (the Redis store) holds the value",
    ],
)
def test_aside_still_flagged(audit_mod, text):
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert any(f.category == "parens-in-prose" for f in findings)


def test_lowercase_required_still_flagged(audit_mod):
    # Arrange
    text = "The full URL (required) must include the scheme."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert any(f.category == "parens-in-prose" for f in findings)


def test_scan_links_flags_missing_target(audit_mod, tmp_path):
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("See [missing](does-not-exist.md) for context.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert any(f.category == "stale-link" for f in findings)


def test_scan_links_ignores_existing_target(audit_mod, tmp_path):
    # Arrange
    target = tmp_path / "real.md"
    target.write_text("# Real")
    doc = tmp_path / "doc.md"
    doc.write_text("See [real](real.md) for context.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert all(f.category != "stale-link" for f in findings)


def test_scan_links_ignores_http(audit_mod, tmp_path):
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("See [example](https://example.com) for context.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert all(f.category != "stale-link" for f in findings)


def test_scan_links_ignores_anchor(audit_mod, tmp_path):
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("See [anchor](#section) here.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert all(f.category != "stale-link" for f in findings)


def test_scan_links_ignores_mailto(audit_mod, tmp_path):
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("Email [me](mailto:a@b.com).")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert all(f.category != "stale-link" for f in findings)


def test_scan_links_handles_anchor_in_path(audit_mod, tmp_path):
    # Arrange
    target = tmp_path / "real.md"
    target.write_text("# Real")
    doc = tmp_path / "doc.md"
    doc.write_text("See [section](real.md#part) for context.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert all(f.category != "stale-link" for f in findings)


def test_scan_links_ignores_links_in_code_fence(audit_mod, tmp_path):
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("Real prose.\n```\n[ghost](missing.md)\n```\n")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert all(f.category != "stale-link" for f in findings)


def test_scan_links_repo_root_fallback(audit_mod, tmp_path):
    # Arrange
    (tmp_path / "standards").mkdir()
    target = tmp_path / "standards" / "real.md"
    target.write_text("# Real")
    nested = tmp_path / "skills" / "feature"
    nested.mkdir(parents=True)
    doc = nested / "SKILL.md"
    doc.write_text("See [real](standards/real.md) for details.")

    # Act
    findings = audit_mod.scan_links(
        "skills/feature/SKILL.md", doc, doc.read_text(), repo_root=tmp_path
    )

    # Assert
    assert all(f.category != "stale-link" for f in findings)


def test_scan_links_repo_root_fallback_still_flags_missing(audit_mod, tmp_path):
    # Arrange
    nested = tmp_path / "skills" / "feature"
    nested.mkdir(parents=True)
    doc = nested / "SKILL.md"
    doc.write_text("See [ghost](nowhere/missing.md) for details.")

    # Act
    findings = audit_mod.scan_links(
        "skills/feature/SKILL.md", doc, doc.read_text(), repo_root=tmp_path
    )

    # Assert
    assert any(f.category == "stale-link" for f in findings)


def test_walk_markdown_skips_excluded_dirs(audit_mod, tmp_path):
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "a.md").write_text("a")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "b.md").write_text("b")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "c.md").write_text("c")

    # Act
    files = list(audit_mod.walk_markdown(tmp_path))

    # Assert
    names = {p.name for p in files}
    assert "a.md" in names
    assert "b.md" not in names
    assert "c.md" not in names


def test_walk_markdown_ignores_non_md(audit_mod, tmp_path):
    # Arrange
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "b.txt").write_text("b")

    # Act
    files = list(audit_mod.walk_markdown(tmp_path))

    # Assert
    names = {p.name for p in files}
    assert names == {"a.md"}


def two_findings(audit_mod):
    return [
        audit_mod.Finding("doc.md", 1, "banned-em-dash", "U+2014", "snippet"),
        audit_mod.Finding("doc.md", 2, "should-bullet", "x", "y"),
    ]


def test_write_jsonl(audit_mod, tmp_path):
    # Arrange
    findings = two_findings(audit_mod)
    jsonl = tmp_path / "out.jsonl"

    # Act
    audit_mod.write_jsonl(findings, jsonl)

    # Assert
    lines = jsonl.read_text().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["category"] == "banned-em-dash"


def test_write_markdown(audit_mod, tmp_path):
    # Arrange
    findings = two_findings(audit_mod)
    md = tmp_path / "out.md"

    # Act
    audit_mod.write_markdown(findings, md)

    # Assert
    md_content = md.read_text()
    assert "Total: 2 findings" in md_content
    assert "should-bullet" in md_content
    assert "doc.md" in md_content


def test_write_markdown_pipe_escape(audit_mod, tmp_path):
    # Arrange
    findings = [
        audit_mod.Finding("doc.md", 1, "x", "with | pipe", "a | b"),
    ]
    md = tmp_path / "out.md"

    # Act
    audit_mod.write_markdown(findings, md)

    # Assert
    content = md.read_text()
    assert r"\|" in content


def test_main_writes_outputs(audit_mod, tmp_path, monkeypatch):
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "doc.md").write_text("- Should validate input.\n")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv",
        [
            "audit-writing-quality.py",
            "--root",
            str(tmp_path),
            "--out-dir",
            str(out_dir),
        ],
    )

    # Act
    code = audit_mod.main()

    # Assert
    assert code == 0
    assert (out_dir / "audit-findings.md").exists()
    assert (out_dir / "audit-findings.jsonl").exists()


def test_main_handles_unreadable_file(audit_mod, tmp_path, monkeypatch):
    # Arrange
    (tmp_path / "rules").mkdir()
    bad = tmp_path / "rules" / "bad.md"
    bad.write_bytes(b"\xff\xfe\xfd")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv",
        [
            "audit-writing-quality.py",
            "--root",
            str(tmp_path),
            "--out-dir",
            str(out_dir),
        ],
    )

    # Act
    code = audit_mod.main()

    # Assert
    assert code == 0


def test_snippet_truncates(audit_mod):
    # Arrange
    long = "x" * 200

    # Act
    snippet = audit_mod.snippet_of(long, length=50)

    # Assert
    assert snippet.endswith("...") is True


def test_snippet_keeps_short_text_whole(audit_mod):
    # Arrange
    short = "x" * 10

    # Act
    snippet = audit_mod.snippet_of(short)

    # Assert
    assert snippet == short

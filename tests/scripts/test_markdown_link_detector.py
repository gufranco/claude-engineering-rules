"""Direct unit tests for scripts/markdown_link_detector.py.

Exercises the shared detection module without going through the
validator subprocess. Source rule: rules/markdown-links.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from markdown_link_detector import (  # noqa: E402
    Finding,
    column_inside_ranges,
    detect_findings,
    find_code_block_ranges,
    find_link_url_ranges,
    is_advisory_file,
    is_already_linked,
    is_file_path_token,
    line_is_inside_ranges,
    resolve_path,
)


def test_is_file_path_token_accepts_extension():
    assert is_file_path_token("README.md")
    assert is_file_path_token("scripts/validate.py")
    assert is_file_path_token("foo/bar/")


def test_is_file_path_token_rejects_short_tokens():
    assert not is_file_path_token(".")
    assert not is_file_path_token("..")
    assert not is_file_path_token("./")
    assert not is_file_path_token("a")


def test_is_file_path_token_rejects_command_with_space():
    assert not is_file_path_token("git status")


def test_is_file_path_token_rejects_option_flag():
    assert not is_file_path_token("--force")


def test_is_file_path_token_rejects_urls():
    assert not is_file_path_token("https://example.com/foo.md")
    assert not is_file_path_token("mailto:a@b.com")


def test_is_file_path_token_rejects_vcs_metadata():
    assert not is_file_path_token(".git")
    assert not is_file_path_token("node_modules/")


def test_is_file_path_token_rejects_plain_words():
    assert not is_file_path_token("README")
    assert not is_file_path_token("hello")


def test_find_code_block_ranges_simple():
    text = "before\n```\ninside\n```\nafter"
    ranges = find_code_block_ranges(text)
    assert ranges == [(2, 4)]


def test_find_code_block_ranges_unclosed():
    text = "before\n```\nstill in block"
    ranges = find_code_block_ranges(text)
    assert ranges == [(2, 3)]


def test_find_code_block_ranges_front_matter():
    text = "---\nfront-matter\n---\nbody"
    ranges = find_code_block_ranges(text)
    assert (1, 3) in ranges


def test_line_is_inside_ranges():
    ranges = [(2, 5)]
    assert not line_is_inside_ranges(1, ranges)
    assert line_is_inside_ranges(2, ranges)
    assert line_is_inside_ranges(5, ranges)
    assert not line_is_inside_ranges(6, ranges)


def test_find_link_url_ranges():
    line = "See [`README.md`](README.md) for details."
    ranges = find_link_url_ranges(line)
    assert ranges
    start, end = ranges[0]
    assert line[start:end] == "README.md"


def test_column_inside_ranges():
    ranges = [(5, 10)]
    assert column_inside_ranges(7, ranges)
    assert not column_inside_ranges(11, ranges)


def test_is_already_linked_backticks_inside_link_text():
    line = "See [`README.md`](README.md) details"
    span_start = line.find("`")
    span_end = line.find("`", span_start + 1) + 1
    assert is_already_linked(line, span_start, span_end)


def test_is_already_linked_not_in_link():
    line = "Plain `README.md` mention"
    span_start = line.find("`")
    span_end = line.find("`", span_start + 1) + 1
    assert not is_already_linked(line, span_start, span_end)


def test_resolve_path_existing_relative():
    doc_dir = REPO_ROOT
    resolved = resolve_path("README.md", doc_dir, REPO_ROOT)
    assert resolved is not None
    assert resolved.name == "README.md"


def test_resolve_path_non_existing():
    doc_dir = REPO_ROOT
    resolved = resolve_path("nowhere/foo.md", doc_dir, REPO_ROOT)
    assert resolved is None


def test_resolve_path_absolute_rejected():
    doc_dir = REPO_ROOT
    resolved = resolve_path("/etc/passwd", doc_dir, REPO_ROOT)
    assert resolved is None


def test_detect_findings_clean_text():
    text = "# Clean\n\nSee [`README.md`](README.md) here.\n"
    findings = detect_findings(text, "tmp.md", REPO_ROOT)
    assert findings == []


def test_detect_findings_bare_reference():
    text = "Look at `README.md` directly.\n"
    findings = detect_findings(text, "tmp.md", REPO_ROOT)
    assert len(findings) == 1
    assert findings[0].token == "README.md"


def test_detect_findings_skips_fenced_block():
    text = "```\nbare `README.md` inside code block\n```\n"
    findings = detect_findings(text, "tmp.md", REPO_ROOT)
    assert findings == []


def test_detect_findings_skips_skip_dir():
    text = "Look at `README.md` directly.\n"
    findings = detect_findings(text, "tests/foo.md", REPO_ROOT)
    assert findings == []


def test_detect_findings_skips_exempt_file():
    text = "Look at `README.md` directly.\n"
    findings = detect_findings(text, "rules/markdown-links.md", REPO_ROOT)
    assert findings == []


def test_finding_render():
    # Build positionally to keep keyword-argument forms out of the file.
    f = Finding("docs/foo.md", 10, 5, "README.md", "README.md")
    rendered = f.render()
    assert "docs/foo.md" in rendered
    assert ":10:5" in rendered
    assert "README.md" in rendered


def test_is_advisory_file_specs_tree():
    assert is_advisory_file("specs/2026-05-21/plan.md")
    assert not is_advisory_file("README.md")
    assert not is_advisory_file("skills/foo/SKILL.md")

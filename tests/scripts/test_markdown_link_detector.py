"""Direct unit tests for scripts/markdown_link_detector.py.

Exercises the shared detection module without going through the
validator subprocess. Source rule: rules/markdown-links.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.markdown_link_detector import (  # noqa: E402
    BrokenLinkFinding,
    Finding,
    column_inside_ranges,
    detect_broken_link_targets,
    detect_findings,
    file_relative_path,
    find_code_block_ranges,
    find_link_url_ranges,
    is_advisory_file,
    is_already_linked,
    is_file_path_token,
    line_is_inside_ranges,
    resolve_path,
    tracked_paths,
)


def test_is_file_path_token_accepts_extension():
    assert is_file_path_token("README.md")
    assert is_file_path_token("hooks/_lib/validate.py")
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


def test_file_relative_path_same_directory():
    doc_dir = REPO_ROOT / "rules"
    target = REPO_ROOT / "rules" / "code-style.md"
    assert file_relative_path(target, doc_dir) == "code-style.md"


def test_file_relative_path_parent_directory():
    doc_dir = REPO_ROOT / "rules"
    target = REPO_ROOT / "checklists" / "checklist.md"
    assert file_relative_path(target, doc_dir) == "../checklists/checklist.md"


def test_file_relative_path_uses_posix_separators():
    doc_dir = REPO_ROOT / "skills" / "review"
    target = REPO_ROOT / "rules" / "code-style.md"
    rel = file_relative_path(target, doc_dir)
    # Even on Windows, the rendered path uses forward slashes.
    assert "\\" not in rel
    assert rel == "../../rules/code-style.md"


def test_broken_link_finding_render_with_correction():
    f = BrokenLinkFinding(
        file="rules/foo.md",
        line=5,
        column=12,
        link_text="`bar.md`",
        link_target="rules/bar.md",
        correct_path="bar.md",
    )
    rendered = f.render()
    assert "rules/foo.md:5:12" in rendered
    assert "rewrite as (bar.md)" in rendered


def test_broken_link_finding_render_without_correction():
    f = BrokenLinkFinding(
        file="docs/foo.md",
        line=1,
        column=1,
        link_text="missing",
        link_target="ghost.md",
        correct_path=None,
    )
    rendered = f.render()
    assert "target not found" in rendered


def test_detect_broken_link_targets_wrong_relative_path(tmp_path):
    # Arrange: two files in subdir/, one with a repo-root-relative link
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "neighbor.md").write_text("# Neighbor\n")
    target_file = tmp_path / "subdir" / "doc.md"
    target_file.write_text("See [`neighbor.md`](subdir/neighbor.md).\n")

    # Act
    findings = detect_broken_link_targets(
        target_file.read_text(),
        str(target_file),
        tmp_path,
    )

    # Assert
    assert len(findings) == 1
    f = findings[0]
    assert f.link_target == "subdir/neighbor.md"
    assert f.correct_path == "neighbor.md"


def test_detect_broken_link_targets_truly_missing(tmp_path):
    # Arrange
    target_file = tmp_path / "doc.md"
    target_file.write_text("See [`ghost.md`](ghost.md).\n")

    # Act
    findings = detect_broken_link_targets(
        target_file.read_text(),
        str(target_file),
        tmp_path,
    )

    # Assert
    assert len(findings) == 1
    assert findings[0].correct_path is None


def test_detect_broken_link_targets_skips_valid_link(tmp_path):
    # Arrange
    (tmp_path / "ok.md").write_text("# OK\n")
    target_file = tmp_path / "doc.md"
    target_file.write_text("See [`ok.md`](ok.md).\n")

    # Act
    findings = detect_broken_link_targets(
        target_file.read_text(),
        str(target_file),
        tmp_path,
    )

    # Assert
    assert findings == []


def test_detect_broken_link_targets_skips_external_urls(tmp_path):
    # Arrange
    target_file = tmp_path / "doc.md"
    target_file.write_text(
        "[anchor](#section), [external](https://example.com), [mail](mailto:a@b).\n"
    )

    # Act
    findings = detect_broken_link_targets(
        target_file.read_text(),
        str(target_file),
        tmp_path,
    )

    # Assert
    assert findings == []


def test_detect_broken_link_targets_ignores_inline_code(tmp_path):
    # Arrange: pattern that looks like a link inside backticks
    target_file = tmp_path / "doc.md"
    target_file.write_text("Use `arr['push'](item)` to mutate.\n")

    # Act
    findings = detect_broken_link_targets(
        target_file.read_text(),
        str(target_file),
        tmp_path,
    )

    # Assert
    assert findings == []


def test_detect_broken_link_targets_skips_fenced_block(tmp_path):
    # Arrange
    target_file = tmp_path / "doc.md"
    target_file.write_text("```\n[broken](nowhere.md)\n```\n")

    # Act
    findings = detect_broken_link_targets(
        target_file.read_text(),
        str(target_file),
        tmp_path,
    )

    # Assert
    assert findings == []


def test_find_code_block_ranges_nested_fences():
    """A 4-backtick fence can contain 3-backtick fences without closing early."""
    text = "before\n````markdown\n```bash\nx\n```\n````\nafter"
    ranges = find_code_block_ranges(text)
    # The outer 4-backtick block spans lines 2-6.
    assert (2, 6) in ranges


def test_find_code_block_ranges_tilde_fences():
    text = "before\n~~~\ncode\n~~~\nafter"
    ranges = find_code_block_ranges(text)
    assert ranges == [(2, 4)]


def test_tracked_paths_lists_files_and_directories():
    paths = tracked_paths(REPO_ROOT)
    # tracked_paths should include some known files
    assert "README.md" in paths
    assert "hooks/_lib/markdown_link_detector.py" in paths
    # And derived directory entries
    assert "hooks" in paths
    assert "hooks/_lib" in paths


def test_tracked_paths_returns_empty_for_non_git_dir(tmp_path):
    paths = tracked_paths(tmp_path)
    assert paths == set()


def test_detect_broken_link_targets_flags_gitignored_target(tmp_path):
    # Arrange: target exists on disk but is not tracked.
    (tmp_path / "untracked.md").write_text("# Not tracked\n")
    target_file = tmp_path / "doc.md"
    target_file.write_text("See [untracked](untracked.md).\n")
    # tracked set deliberately empty: simulates gitignored target
    findings = detect_broken_link_targets(
        target_file.read_text(),
        str(target_file),
        tmp_path,
        tracked=set(),
    )
    assert len(findings) == 1
    assert findings[0].correct_path is None


def test_detect_findings_skips_bare_ref_to_untracked_file(tmp_path):
    # Arrange: file exists on disk but isn't in tracked set
    (tmp_path / "untracked.md").write_text("# Not tracked\n")
    target_file = tmp_path / "doc.md"
    target_file.write_text("Mention `untracked.md` here.\n")
    findings = detect_findings(
        target_file.read_text(),
        str(target_file),
        tmp_path,
        tracked=set(),
    )
    # No findings: detector ignores bare refs whose target is not tracked
    assert findings == []


def test_detect_broken_link_targets_respects_skip_dirs(tmp_path):
    """Files under SKIP_DIR_PREFIXES (tests/, scripts/, .github/, tools/) are skipped."""
    # Arrange
    (tmp_path / "tests").mkdir()
    target_file = tmp_path / "tests" / "fixture.md"
    target_file.write_text("[ghost](ghost.md)\n")

    # Act
    findings = detect_broken_link_targets(
        target_file.read_text(),
        "tests/fixture.md",
        tmp_path,
    )

    # Assert
    assert findings == []

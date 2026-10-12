from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.markdown_link_detector import (  # noqa: E402
    GENERIC_FILENAME_TOKENS,
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


@pytest.mark.parametrize("token", ["README.md", "hooks/_lib/validate.py", "foo/bar/"])
def test_is_file_path_token_accepts_extension(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is True


@pytest.mark.parametrize("token", [".", "..", "./", "a"])
def test_is_file_path_token_rejects_short_tokens(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


def test_is_file_path_token_rejects_command_with_space():
    # Arrange
    candidate = "git status"

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


def test_is_file_path_token_rejects_option_flag():
    # Arrange
    candidate = "--force"

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


@pytest.mark.parametrize("token", ["https://example.com/foo.md", "mailto:a@b.com"])
def test_is_file_path_token_rejects_urls(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


@pytest.mark.parametrize("token", [".git", "node_modules/"])
def test_is_file_path_token_rejects_vcs_metadata(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


@pytest.mark.parametrize("token", ["README", "hello"])
def test_is_file_path_token_rejects_plain_words(token):
    # Arrange
    candidate = token

    # Act
    result = is_file_path_token(candidate)

    # Assert
    assert result is False


def test_find_code_block_ranges_simple():
    # Arrange
    text = "before\n```\ninside\n```\nafter"

    # Act
    ranges = find_code_block_ranges(text)

    # Assert
    assert ranges == [(2, 4)]


def test_find_code_block_ranges_unclosed():
    # Arrange
    text = "before\n```\nstill in block"

    # Act
    ranges = find_code_block_ranges(text)

    # Assert
    assert ranges == [(2, 3)]


def test_find_code_block_ranges_front_matter():
    # Arrange
    text = "---\nfront-matter\n---\nbody"

    # Act
    ranges = find_code_block_ranges(text)

    # Assert
    assert (1, 3) in ranges


@pytest.mark.parametrize(
    ("line", "expected"), [(1, False), (2, True), (5, True), (6, False)]
)
def test_line_is_inside_ranges(line, expected):
    # Arrange
    ranges = [(2, 5)]

    # Act
    result = line_is_inside_ranges(line, ranges)

    # Assert
    assert result is expected


def test_find_link_url_ranges():
    # Arrange
    line = "See [`README.md`](README.md) for details."

    # Act
    ranges = find_link_url_ranges(line)

    # Assert
    assert len(ranges) == 1
    start, end = ranges[0]
    assert line[start:end] == "README.md"


@pytest.mark.parametrize(("column", "expected"), [(7, True), (11, False)])
def test_column_inside_ranges(column, expected):
    # Arrange
    ranges = [(5, 10)]

    # Act
    result = column_inside_ranges(column, ranges)

    # Assert
    assert result is expected


def test_is_already_linked_backticks_inside_link_text():
    # Arrange
    line = "See [`README.md`](README.md) details"
    span_start = line.find("`")
    span_end = line.find("`", span_start + 1) + 1

    # Act
    linked = is_already_linked(line, span_start, span_end)

    # Assert
    assert linked is True


def test_is_already_linked_not_in_link():
    # Arrange
    line = "Plain `README.md` mention"
    span_start = line.find("`")
    span_end = line.find("`", span_start + 1) + 1

    # Act
    linked = is_already_linked(line, span_start, span_end)

    # Assert
    assert linked is False


def test_resolve_path_existing_relative():
    # Arrange
    doc_dir = REPO_ROOT

    # Act
    resolved = resolve_path("README.md", doc_dir, REPO_ROOT)

    # Assert
    assert resolved is not None
    assert resolved.name == "README.md"


def test_resolve_path_non_existing():
    # Arrange
    doc_dir = REPO_ROOT

    # Act
    resolved = resolve_path("nowhere/foo.md", doc_dir, REPO_ROOT)

    # Assert
    assert resolved is None


def test_resolve_path_absolute_rejected():
    # Arrange
    doc_dir = REPO_ROOT

    # Act
    resolved = resolve_path("/etc/passwd", doc_dir, REPO_ROOT)

    # Assert
    assert resolved is None


def test_detect_findings_clean_text():
    # Arrange
    text = "# Clean\n\nSee [`README.md`](README.md) here.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == []


def test_detect_findings_bare_reference():
    # Arrange
    text = "Look at `README.md` directly.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert len(findings) == 1
    assert findings[0].token == "README.md"


def test_detect_findings_skips_fenced_block():
    # Arrange
    text = "```\nbare `README.md` inside code block\n```\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == []


def test_detect_findings_skips_generic_config_filename():
    # Arrange
    text = "Detect the package manager from `package.json`.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == []


@pytest.mark.parametrize("token", sorted(GENERIC_FILENAME_TOKENS))
def test_detect_findings_skips_every_generic_filename_token(token):
    # Arrange
    text = f"Read `{token}` in the target project.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert findings == []


def test_detect_findings_still_flags_repo_owned_path():
    # Arrange
    text = "Look at `rules/markdown-links.md` directly.\n"

    # Act
    findings = detect_findings(text, "tmp.md", REPO_ROOT)

    # Assert
    assert len(findings) == 1
    assert findings[0].token == "rules/markdown-links.md"


def test_detect_findings_skips_skip_dir():
    # Arrange
    text = "Look at `README.md` directly.\n"

    # Act
    findings = detect_findings(text, "tests/foo.md", REPO_ROOT)

    # Assert
    assert findings == []


def test_detect_findings_skips_exempt_file():
    # Arrange
    text = "Look at `README.md` directly.\n"

    # Act
    findings = detect_findings(text, "rules/markdown-links.md", REPO_ROOT)

    # Assert
    assert findings == []


def test_finding_render():
    # Arrange
    f = Finding("docs/foo.md", 10, 5, "README.md", "README.md")

    # Act
    rendered = f.render()

    # Assert
    assert "docs/foo.md" in rendered
    assert ":10:5" in rendered
    assert "README.md" in rendered


@pytest.mark.parametrize(
    ("rel", "expected"),
    [
        ("specs/2026-05-21/plan.md", True),
        ("README.md", False),
        ("skills/foo/SKILL.md", False),
    ],
)
def test_is_advisory_file_specs_tree(rel, expected):
    # Arrange
    path = rel

    # Act
    result = is_advisory_file(path)

    # Assert
    assert result is expected


@pytest.mark.parametrize("rel", [".work/PROMPT.md", ".work-local/plans/x/plan.md"])
def test_is_advisory_file_local_workspace(rel):
    # Arrange
    path = rel

    # Act
    advisory = is_advisory_file(path)

    # Assert
    assert advisory is True


def test_file_relative_path_same_directory():
    # Arrange
    doc_dir = REPO_ROOT / "rules"
    target = REPO_ROOT / "rules" / "code-style.md"

    # Act
    result = file_relative_path(target, doc_dir)

    # Assert
    assert result == "code-style.md"


def test_file_relative_path_parent_directory():
    # Arrange
    doc_dir = REPO_ROOT / "rules"
    target = REPO_ROOT / "checklists" / "checklist.md"

    # Act
    result = file_relative_path(target, doc_dir)

    # Assert
    assert result == "../checklists/checklist.md"


def test_file_relative_path_uses_posix_separators():
    # Arrange
    doc_dir = REPO_ROOT / "skills" / "review"
    target = REPO_ROOT / "rules" / "code-style.md"

    # Act
    rel = file_relative_path(target, doc_dir)

    # Assert
    assert "\\" not in rel
    assert rel == "../../rules/code-style.md"


def test_broken_link_finding_render_with_correction():
    # Arrange
    f = BrokenLinkFinding(
        file="rules/foo.md",
        line=5,
        column=12,
        link_text="`bar.md`",
        link_target="rules/bar.md",
        correct_path="bar.md",
    )

    # Act
    rendered = f.render()

    # Assert
    assert "rules/foo.md:5:12" in rendered
    assert "rewrite as (bar.md)" in rendered


def test_broken_link_finding_render_without_correction():
    # Arrange
    f = BrokenLinkFinding(
        file="docs/foo.md",
        line=1,
        column=1,
        link_text="missing",
        link_target="ghost.md",
        correct_path=None,
    )

    # Act
    rendered = f.render()

    # Assert
    assert "target not found" in rendered


def test_detect_broken_link_targets_wrong_relative_path(tmp_path):
    # Arrange
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
    # Arrange
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
    # Arrange
    text = "before\n````markdown\n```bash\nx\n```\n````\nafter"

    # Act
    ranges = find_code_block_ranges(text)

    # Assert
    assert (2, 6) in ranges


def test_find_code_block_ranges_tilde_fences():
    # Arrange
    text = "before\n~~~\ncode\n~~~\nafter"

    # Act
    ranges = find_code_block_ranges(text)

    # Assert
    assert ranges == [(2, 4)]


def test_tracked_paths_lists_files_and_directories():
    # Arrange
    root = REPO_ROOT

    # Act
    paths = tracked_paths(root)

    # Assert
    assert {
        "README.md",
        "hooks/_lib/markdown_link_detector.py",
        "hooks",
        "hooks/_lib",
    } <= paths


def test_tracked_paths_returns_empty_for_non_git_dir(tmp_path):
    # Arrange
    root = tmp_path

    # Act
    paths = tracked_paths(root)

    # Assert
    assert paths == set()


def test_detect_broken_link_targets_flags_gitignored_target(tmp_path):
    # Arrange
    (tmp_path / "untracked.md").write_text("# Not tracked\n")
    target_file = tmp_path / "doc.md"
    target_file.write_text("See [untracked](untracked.md).\n")

    # Act
    findings = detect_broken_link_targets(
        target_file.read_text(),
        str(target_file),
        tmp_path,
        tracked=set(),
    )

    # Assert
    assert len(findings) == 1
    assert findings[0].correct_path is None


def test_detect_findings_skips_bare_ref_to_untracked_file(tmp_path):
    # Arrange
    (tmp_path / "untracked.md").write_text("# Not tracked\n")
    target_file = tmp_path / "doc.md"
    target_file.write_text("Mention `untracked.md` here.\n")

    # Act
    findings = detect_findings(
        target_file.read_text(),
        str(target_file),
        tmp_path,
        tracked=set(),
    )

    # Assert
    assert findings == []


def test_detect_broken_link_targets_respects_skip_dirs(tmp_path):
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

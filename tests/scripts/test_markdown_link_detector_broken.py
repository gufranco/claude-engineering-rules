from __future__ import annotations


import pytest
from faker import Faker

from _helpers.markdown_link_detector_support import (
    BrokenLinkFinding,
    Finding,
    REPO_ROOT,
    detect_broken_link_targets,
    detect_findings,
    file_relative_path,
    find_code_block_ranges,
    is_advisory_file,
    tracked_paths,
)


def test_finding_render():
    # Arrange
    f = Finding("docs/foo.md", 10, 5, "README.md", "README.md")

    # Act
    rendered = f.render()

    # Assert
    assert rendered == (
        "docs/foo.md:10:5: `README.md` -> existing file at README.md, not linked"
    )


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
    assert rendered == (
        "rules/foo.md:5:12: [`bar.md`](rules/bar.md) -> rewrite as (bar.md)"
    )


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
    assert rendered == "docs/foo.md:1:1: [missing](ghost.md) (target not found in repo)"


def test_detect_broken_link_targets_wrong_relative_path(tmp_path, faker: Faker):
    # Arrange
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "neighbor.md").write_text(f"# {faker.sentence()}\n")
    target_file = tmp_path / "subdir" / "doc.md"
    target_file.write_text("See [`neighbor.md`](subdir/neighbor.md).\n")

    # Act
    findings = detect_broken_link_targets(
        target_file.read_text(),
        str(target_file),
        tmp_path,
    )

    # Assert
    assert [(f.link_target, f.correct_path) for f in findings] == [
        ("subdir/neighbor.md", "neighbor.md")
    ]


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
    assert [(f.link_target, f.correct_path) for f in findings] == [("ghost.md", None)]


def test_detect_broken_link_targets_skips_valid_link(tmp_path, faker: Faker):
    # Arrange
    (tmp_path / "ok.md").write_text(f"# {faker.sentence()}\n")
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
    assert ranges == [(2, 6)]


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


def test_detect_broken_link_targets_flags_gitignored_target(tmp_path, faker: Faker):
    # Arrange
    (tmp_path / "untracked.md").write_text(f"# {faker.sentence()}\n")
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
    assert [(f.link_target, f.correct_path) for f in findings] == [
        ("untracked.md", None)
    ]


def test_detect_findings_skips_bare_ref_to_untracked_file(tmp_path, faker: Faker):
    # Arrange
    (tmp_path / "untracked.md").write_text(f"# {faker.sentence()}\n")
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

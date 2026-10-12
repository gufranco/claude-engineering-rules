from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402

GOOD = """---
date: 2026-08-18
type: concept
tags: [concept]
ai-first: true
---

## For future agent

Why this note exists.

Timeless prose.
"""


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for sub in (
        "wiki/concepts",
        "wiki/entities",
        "raw",
        "daily",
        "templates",
        "_trash",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def test_parse_frontmatter_reads_scalar_keys():
    # Arrange
    text = GOOD

    # Act
    fields = kn.parse_frontmatter(text)

    # Assert
    assert fields is not None
    assert fields["type"] == "concept"
    assert fields["ai-first"] == "true"


def test_parse_frontmatter_skips_list_items():
    # Arrange
    text = GOOD.replace("tags: [concept]", "tags:\n  - concept\n  - idea")

    # Act
    fields = kn.parse_frontmatter(text)

    # Assert
    assert fields is not None
    assert "tags" in fields
    assert "concept" not in fields


def test_parse_frontmatter_returns_none_without_a_block():
    # Arrange
    text = "# Heading\n\nbody\n"

    # Act
    result = kn.parse_frontmatter(text)

    # Assert
    assert result is None


def test_body_after_frontmatter_strips_the_block():
    # Arrange
    text = GOOD

    # Act
    body = kn.body_after_frontmatter(text)

    # Assert
    assert body.lstrip().startswith("## For future agent") is True


def test_body_after_frontmatter_returns_input_when_absent():
    # Arrange
    text = "plain"

    # Act
    result = kn.body_after_frontmatter(text)

    # Assert
    assert result == "plain"


def test_relative_returns_none_outside_the_root(tmp_path):
    # Arrange
    root = tmp_path / "vault"
    root.mkdir()

    # Act
    result = kn.relative(tmp_path / "other.md", root)

    # Assert
    assert result is None


def test_relative_resolves_inside_the_root(vault):
    # Arrange
    path = vault / "wiki/concepts/A.md"

    # Act
    result = kn.relative(path, vault)

    # Assert
    assert result == Path("wiki/concepts/A.md")


@pytest.mark.parametrize(
    "rel,expected",
    [
        ("templates/entity.md", True),
        ("_trash/old.md", True),
        (".obsidian/app.json", True),
        ("CLAUDE.md", True),
        ("wiki/concepts/Real.md", False),
        ("index.md", False),
    ],
)
def test_is_exempt(rel, expected):
    # Arrange
    path = Path(rel)

    # Act
    result = kn.is_exempt(path)

    # Assert
    assert result is expected


@pytest.mark.parametrize(
    "rel,expected",
    [
        ("daily/2026-08-18.md", True),
        ("reviews/week.md", True),
        ("wiki/logs/2026-08-18 - Session.md", True),
        ("wiki/concepts/Idea.md", False),
    ],
)
def test_is_dated_container(rel, expected):
    # Arrange
    path = Path(rel)

    # Act
    result = kn.is_dated_container(path)

    # Assert
    assert result is expected


def test_wikilink_targets_ignores_aliases_and_anchors():
    # Arrange
    text = "See [[Real Person|Alice]] and [[Note#Section]]."

    # Act
    targets = kn.wikilink_targets(text)

    # Assert
    assert targets == ["Real Person", "Note"]


def test_note_titles_skips_exempt_paths(vault):
    # Arrange
    (vault / "wiki/concepts/Kept.md").write_text(GOOD)
    (vault / "templates/entity.md").write_text(GOOD)

    # Act
    titles = kn.note_titles(vault)

    # Assert
    assert "Kept" in titles
    assert "entity" not in titles


def test_iter_notes_yields_only_specced_markdown(vault):
    # Arrange
    (vault / "wiki/concepts/Kept.md").write_text(GOOD)
    (vault / "_trash/Gone.md").write_text(GOOD)
    (vault / "wiki/concepts/data.json").write_text("{}")

    # Act
    found = {rel.name for rel, _text in kn.iter_notes(vault)}

    # Assert
    assert found == {"Kept.md"}


def test_is_volatile_claim_flags_an_undated_count():
    # Arrange
    line = "The backlog has 42 open tasks."

    # Act
    result = kn.is_volatile_claim(line)

    # Assert
    assert result is True


def test_is_volatile_claim_ignores_the_titles_inside_wikilinks():
    # Arrange
    line = (
        "Related: [[Onyx drizzle revert 2026 09 15]], "
        "[[Drizzle has no EXCLUDED and no multi-row UPDATE]]"
    )

    # Act
    result = kn.is_volatile_claim(line)

    # Assert
    assert result is False


def test_is_volatile_claim_still_judges_prose_beside_a_wikilink():
    # Arrange
    line = "The backlog has 42 open tasks, see [[Board]]."

    # Act
    result = kn.is_volatile_claim(line)

    # Assert
    assert result is True


def test_is_volatile_claim_ignores_a_stamped_line():
    # Arrange
    line = "The backlog has 42 tasks (as of 2026-08-18)."

    # Act
    result = kn.is_volatile_claim(line)

    # Assert
    assert result is False


def test_is_volatile_claim_ignores_prose_without_a_number():
    # Arrange
    line = "The backlog is long."

    # Act
    result = kn.is_volatile_claim(line)

    # Assert
    assert result is False


def test_is_volatile_claim_ignores_a_number_without_a_volatile_subject():
    # Arrange
    line = "The book has 42 chapters."

    # Act
    result = kn.is_volatile_claim(line)

    # Assert
    assert result is False


def test_has_stamp_matches_month_precision():
    # Arrange
    line = "Revenue held steady (as of 2026-08)."

    # Act
    result = kn.has_stamp(line)

    # Assert
    assert result is True


def test_stamp_dates_extracts_every_stamp():
    # Arrange
    line = "a (as of 2026-08-18) and b (as of 2026-07)."

    # Act
    dates = kn.stamp_dates(line)

    # Assert
    assert [d.isoformat() for d in dates] == ["2026-08-18", "2026-07-01"]


def test_stamp_dates_ignores_an_impossible_date():
    # Arrange
    line = "(as of 2026-13-45)"

    # Act
    result = kn.stamp_dates(line)

    # Assert
    assert result == []


def test_walk_lines_reports_fence_and_heading_state():
    # Arrange
    body = "\n".join(
        [
            "prose one",
            "```",
            "fenced line",
            "```",
            "## 2026-08-18",
            "under a dated heading",
            "## Plain",
            "under a plain heading",
        ]
    )

    # Act
    rows = list(kn.walk_lines(body))

    # Assert
    visible = {text: dated for _number, text, dated in rows}
    assert "fenced line" not in visible
    assert visible["prose one"] is False
    assert visible["under a dated heading"] is True
    assert visible["under a plain heading"] is False


def test_walk_lines_skips_blank_lines_and_headings():
    # Arrange
    body = "first\n\n## Heading\n\nsecond\n"

    # Act
    rows = list(kn.walk_lines(body))

    # Assert
    assert [text for _number, text, _dated in rows] == ["first", "second"]


def test_vault_root_reads_the_environment(monkeypatch, vault):
    # Arrange
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault))

    # Act
    result = kn.vault_root()

    # Assert
    assert result == vault


def test_vault_root_returns_none_when_missing(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(tmp_path / "absent"))

    # Act
    result = kn.vault_root()

    # Assert
    assert result is None


def test_is_volatile_claim_ignores_a_date_prefixed_snapshot():
    # Arrange
    line = "- 2026-08-18: the backlog has 42 open tasks"

    # Act
    result = kn.is_volatile_claim(line)

    # Assert
    assert result is False


def test_in_vault_accepts_a_path_inside_the_root(monkeypatch, vault):
    # Arrange
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault))

    # Act
    result = kn.in_vault(str(vault / "wiki/concepts/A.md"))

    # Assert
    assert result is True


def test_in_vault_rejects_a_path_outside_the_root(monkeypatch, vault, tmp_path):
    # Arrange
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault))

    # Act
    result = kn.in_vault(str(tmp_path / "elsewhere.md"))

    # Assert
    assert result is False


def test_in_vault_rejects_an_empty_path(monkeypatch, vault):
    # Arrange
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault))

    # Act
    result = kn.in_vault("")

    # Assert
    assert result is False


def test_in_vault_is_false_when_no_vault_exists(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(tmp_path / "absent"))

    # Act
    result = kn.in_vault(str(tmp_path / "absent" / "note.md"))

    # Assert
    assert result is False


@pytest.mark.parametrize(
    "rel",
    [".pytest_cache/README.md", ".git/COMMIT_EDITMSG.md", ".github/workflows/notes.md"],
)
def test_is_exempt_skips_hidden_directories(rel):
    # Arrange
    path = Path(rel)

    # Act
    result = kn.is_exempt(path)

    # Assert
    assert result is True

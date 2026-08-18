"""Coverage for the shared knowledge-note primitives.

Source rule: rules/knowledge-notes.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn

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
    for sub in ("wiki/concepts", "wiki/entities", "raw", "daily", "templates", "_trash"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def test_parse_frontmatter_reads_scalar_keys():
    fields = kn.parse_frontmatter(GOOD)

    assert fields is not None
    assert fields["type"] == "concept"
    assert fields["ai-first"] == "true"


def test_parse_frontmatter_skips_list_items():
    text = GOOD.replace("tags: [concept]", "tags:\n  - concept\n  - idea")

    fields = kn.parse_frontmatter(text)

    assert fields is not None
    assert "tags" in fields
    assert "concept" not in fields


def test_parse_frontmatter_returns_none_without_a_block():
    assert kn.parse_frontmatter("# Heading\n\nbody\n") is None


def test_body_after_frontmatter_strips_the_block():
    body = kn.body_after_frontmatter(GOOD)

    assert body.lstrip().startswith("## For future agent")


def test_body_after_frontmatter_returns_input_when_absent():
    assert kn.body_after_frontmatter("plain") == "plain"


def test_relative_returns_none_outside_the_root(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()

    assert kn.relative(tmp_path / "other.md", root) is None


def test_relative_resolves_inside_the_root(vault):
    result = kn.relative(vault / "wiki/concepts/A.md", vault)

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
    assert kn.is_exempt(Path(rel)) is expected


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
    assert kn.is_dated_container(Path(rel)) is expected


def test_wikilink_targets_ignores_aliases_and_anchors():
    targets = kn.wikilink_targets("See [[Real Person|Alice]] and [[Note#Section]].")

    assert targets == ["Real Person", "Note"]


def test_note_titles_skips_exempt_paths(vault):
    (vault / "wiki/concepts/Kept.md").write_text(GOOD)
    (vault / "templates/entity.md").write_text(GOOD)

    titles = kn.note_titles(vault)

    assert "Kept" in titles
    assert "entity" not in titles


def test_iter_notes_yields_only_specced_markdown(vault):
    (vault / "wiki/concepts/Kept.md").write_text(GOOD)
    (vault / "_trash/Gone.md").write_text(GOOD)
    (vault / "wiki/concepts/data.json").write_text("{}")

    found = {rel.name for rel, _text in kn.iter_notes(vault)}

    assert found == {"Kept.md"}


def test_is_volatile_claim_flags_an_undated_count():
    assert kn.is_volatile_claim("The backlog has 42 open tasks.") is True


def test_is_volatile_claim_ignores_a_stamped_line():
    assert kn.is_volatile_claim("The backlog has 42 tasks (as of 2026-08-18).") is False


def test_is_volatile_claim_ignores_prose_without_a_number():
    assert kn.is_volatile_claim("The backlog is long.") is False


def test_is_volatile_claim_ignores_a_number_without_a_volatile_subject():
    assert kn.is_volatile_claim("The book has 42 chapters.") is False


def test_has_stamp_matches_month_precision():
    assert kn.has_stamp("Revenue held steady (as of 2026-08).") is True


def test_stamp_dates_extracts_every_stamp():
    dates = kn.stamp_dates("a (as of 2026-08-18) and b (as of 2026-07).")

    assert [d.isoformat() for d in dates] == ["2026-08-18", "2026-07-01"]


def test_stamp_dates_ignores_an_impossible_date():
    assert kn.stamp_dates("(as of 2026-13-45)") == []


def test_walk_lines_reports_fence_and_heading_state():
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

    rows = list(kn.walk_lines(body))
    visible = {text: dated for _number, text, dated in rows}

    assert "fenced line" not in visible
    assert visible["prose one"] is False
    assert visible["under a dated heading"] is True
    assert visible["under a plain heading"] is False


def test_walk_lines_skips_blank_lines_and_headings():
    rows = list(kn.walk_lines("first\n\n## Heading\n\nsecond\n"))

    assert [text for _number, text, _dated in rows] == ["first", "second"]


def test_vault_root_reads_the_environment(monkeypatch, vault):
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault))

    assert kn.vault_root() == vault


def test_vault_root_returns_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(tmp_path / "absent"))

    assert kn.vault_root() is None


def test_is_volatile_claim_ignores_a_date_prefixed_snapshot():
    assert kn.is_volatile_claim("- 2026-08-18: the backlog has 42 open tasks") is False

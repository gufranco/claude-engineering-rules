from __future__ import annotations

from pathlib import Path
from types import ModuleType

from faker import Faker


def test_scan_links_flags_missing_target(audit_mod: ModuleType, tmp_path: Path) -> None:
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("See [missing](does-not-exist.md) for context.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert [f.category for f in findings] == ["stale-link"]


def test_scan_links_ignores_existing_target(
    audit_mod: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    target = tmp_path / "real.md"
    target.write_text("# Real")
    doc = tmp_path / "doc.md"
    doc.write_text("See [real](real.md) for context.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert [f.category for f in findings] == []


def test_scan_links_ignores_http(audit_mod: ModuleType, tmp_path: Path) -> None:
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("See [example](https://example.com) for context.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert [f.category for f in findings] == []


def test_scan_links_ignores_anchor(audit_mod: ModuleType, tmp_path: Path) -> None:
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("See [anchor](#section) here.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert [f.category for f in findings] == []


def test_scan_links_ignores_mailto(audit_mod: ModuleType, tmp_path: Path) -> None:
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("Email [me](mailto:a@b.com).")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert [f.category for f in findings] == []


def test_scan_links_handles_anchor_in_path(
    audit_mod: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    target = tmp_path / "real.md"
    target.write_text("# Real")
    doc = tmp_path / "doc.md"
    doc.write_text("See [section](real.md#part) for context.")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert [f.category for f in findings] == []


def test_scan_links_ignores_links_in_code_fence(
    audit_mod: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("Real prose.\n```\n[ghost](missing.md)\n```\n")

    # Act
    findings = audit_mod.scan_links("doc.md", doc, doc.read_text())

    # Assert
    assert [f.category for f in findings] == []


def test_scan_links_repo_root_fallback(audit_mod: ModuleType, tmp_path: Path) -> None:
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
    assert [f.category for f in findings] == []


def test_scan_links_repo_root_fallback_still_flags_missing(
    audit_mod: ModuleType, tmp_path: Path
) -> None:
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
    assert [f.category for f in findings] == ["stale-link"]


def test_walk_markdown_skips_excluded_dirs(
    audit_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    for directory, name in [("rules", "a.md"), ("specs", "b.md"), (".git", "c.md")]:
        (tmp_path / directory).mkdir()
        (tmp_path / directory / name).write_text(faker.sentence())

    # Act
    files = list(audit_mod.walk_markdown(tmp_path))

    # Assert
    assert files == [tmp_path / "rules" / "a.md"]


def test_walk_markdown_ignores_non_md(
    audit_mod: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    (tmp_path / "a.md").write_text(faker.sentence())
    (tmp_path / "b.txt").write_text(faker.sentence())

    # Act
    files = list(audit_mod.walk_markdown(tmp_path))

    # Assert
    assert files == [tmp_path / "a.md"]

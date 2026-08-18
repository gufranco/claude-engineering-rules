"""Coverage for the vault-health linter.

Source rule: rules/knowledge-notes.md.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "vault-health.py"


def load():
    import sys

    spec = importlib.util.spec_from_file_location("vault_health", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["vault_health"] = module
    spec.loader.exec_module(module)
    return module


def note(title: str, body: str = "Timeless prose.") -> str:
    return (
        "---\n"
        "date: 2026-08-18\n"
        "type: concept\n"
        "tags: [concept]\n"
        "ai-first: true\n"
        "---\n\n"
        "## For future agent\n\n"
        f"Why {title} exists.\n\n"
        f"{body}\n"
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for sub in ("wiki/concepts", "wiki/entities", "daily", "_trash"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "index.md").write_text(note("index"))
    (root / "log.md").write_text(note("log"))
    return root


def run(vault: Path, *args: str):
    module = load()
    return module.audit(vault)


def test_a_clean_vault_reports_nothing(vault):
    (vault / "wiki/concepts/A.md").write_text(note("A", "Links to [[B]]."))
    (vault / "wiki/concepts/B.md").write_text(note("B", "Links to [[A]]."))
    (vault / "index.md").write_text(note("index", "Holds [[A]] and [[B]]."))

    findings = run(vault)

    assert [f for f in findings if f.code in {"VH001", "VH002", "VH003"}] == []


def test_reports_a_missing_required_key(vault):
    text = note("A").replace("ai-first: true\n", "")
    (vault / "wiki/concepts/A.md").write_text(text)

    codes = {f.code for f in run(vault)}

    assert "VH001" in codes


def test_reports_a_missing_frontmatter_block(vault):
    (vault / "wiki/concepts/A.md").write_text("# Bare\n\nbody\n")

    codes = {f.code for f in run(vault)}

    assert "VH001" in codes


def test_reports_a_missing_preamble(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("A").replace("## For future agent", "## Summary")
    )

    codes = {f.code for f in run(vault)}

    assert "VH002" in codes


def test_reports_a_broken_wikilink(vault):
    (vault / "wiki/concepts/A.md").write_text(note("A", "Points at [[Absent]]."))

    broken = [f for f in run(vault) if f.code == "VH003"]

    assert broken and "Absent" in broken[0].detail


def test_a_link_marked_tbd_is_not_broken(vault):
    (vault / "wiki/concepts/A.md").write_text(note("A", "Points at [[Absent]], TBD."))

    assert [f for f in run(vault) if f.code == "VH003"] == []


def test_reports_an_orphan(vault):
    (vault / "wiki/concepts/Lonely.md").write_text(
        note("Lonely", "Nothing points here.")
    )

    orphans = [f for f in run(vault) if f.code == "VH004"]

    assert orphans and "Lonely" in orphans[0].path


def test_a_linked_note_is_not_an_orphan(vault):
    (vault / "wiki/concepts/A.md").write_text(note("A", "Points at [[B]]."))
    (vault / "wiki/concepts/B.md").write_text(note("B", "Points back at [[A]]."))

    orphan_paths = {f.path for f in run(vault) if f.code == "VH004"}

    assert "wiki/concepts/B.md" not in orphan_paths


def test_dated_notes_are_never_orphans(vault):
    (vault / "daily/2026-08-18.md").write_text(note("today"))

    orphan_paths = {f.path for f in run(vault) if f.code == "VH004"}

    assert "daily/2026-08-18.md" not in orphan_paths


def test_reports_a_duplicate_title(vault):
    (vault / "wiki/concepts/Same.md").write_text(note("Same"))
    (vault / "wiki/entities/Same.md").write_text(note("Same"))

    duplicates = [f for f in run(vault) if f.code == "VH005"]

    assert duplicates


def test_reports_index_drift(vault):
    (vault / "wiki/concepts/A.md").write_text(note("A", "Points at [[B]]."))
    (vault / "wiki/concepts/B.md").write_text(note("B", "Points at [[A]]."))

    drift = {f.path for f in run(vault) if f.code == "VH006"}

    assert "wiki/concepts/A.md" in drift


def test_a_note_named_in_the_index_is_not_drift(vault):
    (vault / "index.md").write_text(note("index", "Holds [[A]]."))
    (vault / "wiki/concepts/A.md").write_text(note("A", "Points at [[index]]."))

    drift = {f.path for f in run(vault) if f.code == "VH006"}

    assert "wiki/concepts/A.md" not in drift


def test_reports_a_note_with_no_outbound_links(vault):
    (vault / "index.md").write_text(note("index", "Holds [[A]]."))
    (vault / "wiki/concepts/A.md").write_text(note("A", "Says nothing about anything."))

    isolated = [f for f in run(vault) if f.code == "VH007"]

    assert isolated and isolated[0].path == "wiki/concepts/A.md"


def test_trash_and_templates_are_ignored(vault):
    (vault / "_trash/Old.md").write_text("garbage with no frontmatter")

    paths = {f.path for f in run(vault)}

    assert "_trash/Old.md" not in paths


def test_main_returns_zero_without_strict(vault, capsys):
    (vault / "wiki/concepts/A.md").write_text("# Bare\n\nbody\n")
    module = load()

    code = module.main(["--path", str(vault)])

    assert code == 0
    assert "VH001" in capsys.readouterr().out


def test_main_returns_one_with_strict_and_errors(vault):
    (vault / "wiki/concepts/A.md").write_text("# Bare\n\nbody\n")
    module = load()

    assert module.main(["--path", str(vault), "--strict"]) == 1


def test_main_returns_zero_with_strict_and_only_warnings(vault):
    (vault / "index.md").write_text(note("index", "Holds [[A]]."))
    (vault / "wiki/concepts/A.md").write_text(note("A", "Points at [[index]]."))
    module = load()

    assert module.main(["--path", str(vault), "--strict"]) == 0


def test_main_emits_json(vault, capsys):
    (vault / "wiki/concepts/A.md").write_text("# Bare\n\nbody\n")
    module = load()

    module.main(["--path", str(vault), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["error"] >= 1
    assert payload["findings"][0]["code"]


def test_main_reports_a_clean_vault(vault, capsys):
    module = load()

    code = module.main(["--path", str(vault)])

    assert code == 0
    assert "clean" in capsys.readouterr().out.lower()


def test_main_errors_when_the_vault_is_missing(tmp_path, capsys):
    module = load()

    code = module.main(["--path", str(tmp_path / "absent")])

    assert code == 2
    assert "not a directory" in capsys.readouterr().err.lower()

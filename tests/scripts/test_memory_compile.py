from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "memory-compile.py"


def load():
    spec = importlib.util.spec_from_file_location("memory_compile", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["memory_compile"] = module
    spec.loader.exec_module(module)
    return module


def note(
    title: str, scope: str = "project", memory: str = "true", body: str = "The claim."
) -> str:
    return (
        "---\n"
        "date: 2026-08-18\n"
        "type: concept\n"
        "tags: [concept]\n"
        "ai-first: true\n"
        f"memory: {memory}\n"
        f"memory-scope: {scope}\n"
        f"description: What {title} covers\n"
        "---\n\n"
        "## For future agent\n\n"
        f"Why {title} exists.\n\n"
        f"{body}\n"
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "wiki/concepts").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def memory(tmp_path: Path) -> Path:
    target = tmp_path / "memory"
    target.mkdir(parents=True, exist_ok=True)
    return target


def test_collects_only_opted_in_notes(vault):
    # Arrange
    module = load()
    (vault / "wiki/concepts/In.md").write_text(note("In"))
    (vault / "wiki/concepts/Out.md").write_text(note("Out", memory="false"))

    # Act
    entries = module.collect(vault)

    # Assert
    assert [entry.slug for entry in entries] == ["in"]


def test_a_note_without_a_scope_is_not_collected(vault):
    # Arrange
    module = load()
    text = note("In").replace("memory-scope: project\n", "")
    (vault / "wiki/concepts/In.md").write_text(text)

    # Act
    result = module.collect(vault)

    # Assert
    assert result == []


def test_an_unknown_scope_is_not_collected(vault):
    # Arrange
    module = load()
    (vault / "wiki/concepts/In.md").write_text(note("In", scope="nonsense"))

    # Act
    result = module.collect(vault)

    # Assert
    assert result == []


def test_render_carries_provenance(vault):
    # Arrange
    module = load()
    (vault / "wiki/concepts/In.md").write_text(note("In"))
    entry = module.collect(vault)[0]

    # Act
    text = module.render(entry)

    # Assert
    assert "generated_from: wiki/concepts/In.md" in text
    assert "type: project" in text
    assert "name: in" in text


def test_render_index_lists_every_entry(vault):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    (vault / "wiki/concepts/B.md").write_text(note("B", scope="feedback"))
    entries = module.collect(vault)

    # Act
    index = module.render_index(entries)

    # Assert
    assert "a.md" in index
    assert "b.md" in index
    assert "generated" in index.lower()


def test_plan_reports_creations(vault, memory):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))

    # Act
    plan = module.plan(vault, memory)

    # Assert
    assert plan["create"] == ["a.md", "MEMORY.md"]
    assert plan["unmanaged"] == []


def test_plan_is_idempotent(vault, memory):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    module.apply(module.plan(vault, memory), memory, backup_dir=None)

    # Act
    plan = module.plan(vault, memory)

    # Assert
    assert plan["create"] == []
    assert plan["update"] == []


def test_plan_reports_an_update_when_the_note_changed(vault, memory):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    module.apply(module.plan(vault, memory), memory, backup_dir=None)
    (vault / "wiki/concepts/A.md").write_text(note("A", body="A different claim."))

    # Act
    plan = module.plan(vault, memory)

    # Assert
    assert plan["update"] == ["a.md"]


def test_a_hand_written_memory_file_is_never_touched(vault, memory):
    # Arrange
    module = load()
    (memory / "handmade.md").write_text(
        "---\nname: handmade\ntype: project\n---\n\nMine.\n"
    )
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    plan = module.plan(vault, memory)

    # Act
    module.apply(plan, memory, backup_dir=None)

    # Assert
    assert plan["unmanaged"] == ["handmade.md"]
    assert (memory / "handmade.md").read_text().endswith("Mine.\n")


def test_a_generated_file_whose_note_disappeared_is_demoted(vault, memory):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    module.apply(module.plan(vault, memory), memory, backup_dir=None)
    (vault / "wiki/concepts/A.md").unlink()

    # Act
    plan = module.plan(vault, memory)

    # Assert
    assert plan["demote"] == ["a.md"]


def test_apply_writes_the_files(vault, memory):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))

    # Act
    module.apply(module.plan(vault, memory), memory, backup_dir=None)

    # Assert
    assert (memory / "a.md").exists()
    assert (memory / "MEMORY.md").exists()


def test_apply_demotes_by_moving_not_deleting(vault, memory):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    module.apply(module.plan(vault, memory), memory, backup_dir=None)
    (vault / "wiki/concepts/A.md").unlink()

    # Act
    module.apply(module.plan(vault, memory), memory, backup_dir=None)

    # Assert
    assert not (memory / "a.md").exists()
    assert (memory / "_demoted" / "a.md").exists()


def test_apply_backs_up_before_writing(vault, memory, tmp_path):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    module.apply(module.plan(vault, memory), memory, backup_dir=None)
    (vault / "wiki/concepts/A.md").write_text(note("A", body="Changed."))
    backups = tmp_path / "backups"

    # Act
    module.apply(module.plan(vault, memory), memory, backup_dir=backups)

    # Assert
    copies = list(backups.rglob("a.md"))
    assert len(copies) == 1
    assert "Changed." not in copies[0].read_text()


def test_the_budget_demotes_the_lowest_priority_scope(vault, memory):
    # Arrange
    module = load()
    long_body = "word " * 400
    (vault / "wiki/concepts/Keep.md").write_text(
        note("Keep", scope="user", body=long_body)
    )
    (vault / "wiki/concepts/Drop.md").write_text(
        note("Drop", scope="reference", body=long_body)
    )

    # Act
    plan = module.plan(vault, memory, budget=3000)

    # Assert
    assert "keep.md" in plan["create"]
    assert "drop.md" not in plan["create"]
    assert plan["over_budget"] == ["drop.md"]


def test_nothing_is_over_budget_when_the_budget_is_generous(vault, memory):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))

    # Act
    plan = module.plan(vault, memory, budget=1_000_000)

    # Assert
    assert plan["over_budget"] == []


def test_main_defaults_to_a_dry_run(vault, memory, capsys):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))

    # Act
    code = module.main(["--path", str(vault), "--memory", str(memory)])

    # Assert
    assert code == 0
    assert not (memory / "a.md").exists()
    assert "dry run" in capsys.readouterr().out.lower()


def test_main_applies_when_asked(vault, memory):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))

    # Act
    code = module.main(["--path", str(vault), "--memory", str(memory), "--apply"])

    # Assert
    assert code == 0
    assert (memory / "a.md").exists()


def test_main_emits_json(vault, memory, capsys):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))

    # Act
    module.main(["--path", str(vault), "--memory", str(memory), "--json"])

    # Assert
    payload = json.loads(capsys.readouterr().out)
    assert payload["create"] == ["a.md", "MEMORY.md"]


def test_main_errors_without_a_vault(tmp_path, capsys):
    # Arrange
    module = load()

    # Act
    code = module.main(["--path", str(tmp_path / "absent"), "--memory", str(tmp_path)])

    # Assert
    assert code == 2
    assert "not a directory" in capsys.readouterr().err.lower()


def test_main_errors_without_a_memory_directory(vault, tmp_path, capsys):
    # Arrange
    module = load()

    # Act
    code = module.main(["--path", str(vault), "--memory", str(tmp_path / "absent")])

    # Assert
    assert code == 2
    assert "memory" in capsys.readouterr().err.lower()


def test_main_reports_nothing_to_do(vault, memory, capsys):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    module.main(["--path", str(vault), "--memory", str(memory), "--apply"])
    capsys.readouterr()

    # Act
    code = module.main(["--path", str(vault), "--memory", str(memory)])

    # Assert
    assert code == 0
    assert "nothing" in capsys.readouterr().out.lower()


def test_the_index_is_created_even_when_no_note_opted_in(vault, memory):
    # Arrange
    module = load()

    # Act
    module.main(["--path", str(vault), "--memory", str(memory), "--apply"])

    # Assert
    assert (memory / "MEMORY.md").exists()
    assert "opted into memory" in (memory / "MEMORY.md").read_text()


def test_a_note_without_frontmatter_is_skipped(vault):
    # Arrange
    module = load()
    (vault / "wiki/concepts/Bare.md").write_text("# Bare\n\nno frontmatter\n")

    # Act
    result = module.collect(vault)

    # Assert
    assert result == []


def test_a_hand_written_file_wins_a_name_collision(vault, memory):
    # Arrange
    module = load()
    (memory / "a.md").write_text("---\nname: a\ntype: project\n---\n\nHand written.\n")
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    prepared = module.plan(vault, memory)

    # Act
    module.apply(prepared, memory, backup_dir=None)

    # Assert
    assert prepared["unmanaged"] == ["a.md"]
    assert "a.md" not in prepared["create"]
    assert (memory / "a.md").read_text().endswith("Hand written.\n")


def test_apply_refuses_an_unmanaged_file_even_if_a_plan_names_it(vault, memory):
    # Arrange
    module = load()
    (memory / "a.md").write_text("---\nname: a\ntype: project\n---\n\nHand written.\n")
    hostile = {
        "create": ["a.md"],
        "update": [],
        "demote": [],
        "unmanaged": ["a.md"],
        "over_budget": [],
        "rendered": {"a.md": "generated content"},
        "spent": 0,
        "budget": 100,
    }

    # Act
    module.apply(hostile, memory, backup_dir=None)

    # Assert
    assert (memory / "a.md").read_text().endswith("Hand written.\n")


def test_a_hand_written_index_is_never_overwritten(vault, memory):
    # Arrange
    module = load()
    (memory / "MEMORY.md").write_text("# Memory\n\n- [handmade](handmade.md) - mine\n")
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    prepared = module.plan(vault, memory)

    # Act
    module.apply(prepared, memory, backup_dir=None)

    # Assert
    assert "MEMORY.md" in prepared["unmanaged"]
    assert "MEMORY.md" not in prepared["update"]
    assert "handmade" in (memory / "MEMORY.md").read_text()


def test_a_generated_index_is_updated(vault, memory):
    # Arrange
    module = load()
    (vault / "wiki/concepts/A.md").write_text(note("A"))
    module.apply(module.plan(vault, memory), memory, backup_dir=None)
    (vault / "wiki/concepts/B.md").write_text(note("B"))

    # Act
    prepared = module.plan(vault, memory)

    # Assert
    assert "MEMORY.md" in prepared["update"]

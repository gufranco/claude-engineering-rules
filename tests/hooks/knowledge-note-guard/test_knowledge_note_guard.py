"""Coverage for the knowledge-note-guard hook.

Source rule: rules/knowledge-notes.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

HOOK = "knowledge-note-guard"

GOOD = """---
date: 2026-08-18
type: concept
tags: [concept]
ai-first: true
---

## For future agent

What this note holds and why it was saved.

Some timeless prose about the idea.
"""


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for sub in ("wiki/concepts", "wiki/entities", "raw/articles", "daily", "templates", "_trash"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def env(vault: Path) -> dict[str, str]:
    return {"SECOND_BRAIN_VAULT": str(vault)}


def note(vault: Path, rel: str) -> str:
    return str(vault / rel)


def test_allows_compliant_note(tool_use, assert_allows, vault, env):
    payload = tool_use("Write", {"file_path": note(vault, "wiki/concepts/Idea.md"), "content": GOOD})

    assert_allows(HOOK, payload, env=env)


def test_allows_path_outside_the_vault(tool_use, assert_allows, tmp_path, env):
    outside = tmp_path / "elsewhere.md"
    payload = tool_use("Write", {"file_path": str(outside), "content": "no frontmatter here"})

    assert_allows(HOOK, payload, env=env)


def test_allows_non_markdown_inside_the_vault(tool_use, assert_allows, vault, env):
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/data.json"), "content": "{}"}
    )

    assert_allows(HOOK, payload, env=env)


@pytest.mark.parametrize("rel", ["templates/entity.md", "_trash/old.md", ".obsidian/app.json"])
def test_allows_exempt_directories(tool_use, assert_allows, vault, env, rel):
    payload = tool_use("Write", {"file_path": note(vault, rel), "content": "anything at all"})

    assert_allows(HOOK, payload, env=env)


def test_allows_vault_root_manual_without_frontmatter(tool_use, assert_allows, vault, env):
    payload = tool_use("Write", {"file_path": note(vault, "CLAUDE.md"), "content": "# Manual\n"})

    assert_allows(HOOK, payload, env=env)


def test_blocks_missing_frontmatter(tool_use, assert_blocks, vault, env):
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Bare.md"), "content": "# Bare\n\nno frontmatter\n"},
    )

    assert_blocks(HOOK, payload, "KN001", env=env)


def test_blocks_missing_required_key(tool_use, assert_blocks, vault, env):
    content = GOOD.replace("ai-first: true\n", "")
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Partial.md"), "content": content}
    )

    assert_blocks(HOOK, payload, "ai-first", env=env)


def test_blocks_missing_preamble(tool_use, assert_blocks, vault, env):
    content = GOOD.replace("## For future agent", "## Summary")
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/NoPreamble.md"), "content": content}
    )

    assert_blocks(HOOK, payload, "KN002", env=env)


def test_blocks_undated_volatile_claim(tool_use, assert_blocks, vault, env):
    content = GOOD + "\nThe pipeline has 13 open deals.\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Rot.md"), "content": content}
    )

    assert_blocks(HOOK, payload, "KN003", env=env)


def test_allows_stamped_volatile_claim(tool_use, assert_allows, vault, env):
    content = GOOD + "\nThe pipeline has 13 open deals (as of 2026-08-18).\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Stamped.md"), "content": content}
    )

    assert_allows(HOOK, payload, env=env)


def test_allows_volatile_claim_in_dated_container(tool_use, assert_allows, vault, env):
    content = GOOD + "\nThe pipeline has 13 open deals.\n"
    payload = tool_use("Write", {"file_path": note(vault, "daily/2026-08-18.md"), "content": content})

    assert_allows(HOOK, payload, env=env)


def test_allows_volatile_claim_under_dated_heading(tool_use, assert_allows, vault, env):
    content = GOOD + "\n## 2026-08-18\n\nThe pipeline has 13 open deals.\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Snapshot.md"), "content": content}
    )

    assert_allows(HOOK, payload, env=env)


def test_ignores_volatile_claim_inside_a_code_fence(tool_use, assert_allows, vault, env):
    content = GOOD + "\n```\nThe pipeline has 13 open deals.\n```\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Fenced.md"), "content": content}
    )

    assert_allows(HOOK, payload, env=env)


def test_blocks_wikilink_to_a_note_that_does_not_exist(tool_use, assert_blocks, vault, env):
    content = GOOD + "\nSee [[Nonexistent Person]] for context.\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Linker.md"), "content": content}
    )

    assert_blocks(HOOK, payload, "KN004", env=env)


def test_allows_wikilink_to_an_existing_note(tool_use, assert_allows, vault, env):
    (vault / "wiki/entities/Real Person.md").write_text(GOOD)
    content = GOOD + "\nSee [[Real Person]] for context.\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Linker.md"), "content": content}
    )

    assert_allows(HOOK, payload, env=env)


def test_allows_wikilink_marked_tbd(tool_use, assert_allows, vault, env):
    content = GOOD + "\nSee [[Future Note]], TBD until it is written.\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Pending.md"), "content": content}
    )

    assert_allows(HOOK, payload, env=env)


def test_blocks_edit_of_an_existing_raw_source(tool_use, assert_blocks, vault, env):
    source = vault / "raw/articles/Piece.md"
    source.write_text(GOOD)
    payload = tool_use(
        "Edit",
        {"file_path": str(source), "old_string": "timeless prose", "new_string": "rewritten prose"},
    )

    assert_blocks(HOOK, payload, "KN005", env=env)


def test_allows_creating_a_new_raw_source(tool_use, assert_allows, vault, env):
    payload = tool_use(
        "Write", {"file_path": note(vault, "raw/articles/Fresh.md"), "content": GOOD}
    )

    assert_allows(HOOK, payload, env=env)


def test_blocks_removal_of_a_vault_note(tool_use, assert_blocks, vault, env):
    target = vault / "wiki/concepts/Doomed.md"
    target.write_text(GOOD)
    payload = tool_use("Bash", {"command": f"rm {target}"})

    assert_blocks(HOOK, payload, "KN006", env=env)


def test_allows_removal_inside_the_trash_folder(tool_use, assert_allows, vault, env):
    payload = tool_use("Bash", {"command": f"rm {vault / '_trash/old.md'}"})

    assert_allows(HOOK, payload, env=env)


def test_allows_removal_outside_the_vault(tool_use, assert_allows, tmp_path, env):
    payload = tool_use("Bash", {"command": f"rm {tmp_path / 'scratch.txt'}"})

    assert_allows(HOOK, payload, env=env)


def test_allows_bash_without_a_removal(tool_use, assert_allows, vault, env):
    payload = tool_use("Bash", {"command": f"cat {vault / 'index.md'}"})

    assert_allows(HOOK, payload, env=env)


def test_edit_composes_the_post_edit_text(tool_use, assert_blocks, vault, env):
    target = vault / "wiki/concepts/Growing.md"
    target.write_text(GOOD)
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "Some timeless prose about the idea.",
            "new_string": "The backlog has 42 open tasks.",
        },
    )

    assert_blocks(HOOK, payload, "KN003", env=env)


def test_multiedit_composes_every_edit(tool_use, assert_blocks, vault, env):
    target = vault / "wiki/concepts/Multi.md"
    target.write_text(GOOD)
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": str(target),
            "edits": [
                {"old_string": "Some timeless prose about the idea.", "new_string": "Filler."},
                {"old_string": "Filler.", "new_string": "The backlog has 42 open tasks."},
            ],
        },
    )

    assert_blocks(HOOK, payload, "KN003", env=env)


def test_bypass_env_allows_everything(tool_use, assert_allows, vault, env):
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Bare.md"), "content": "nothing here"}
    )

    assert_allows(HOOK, payload, env={**env, "KNOWLEDGE_NOTE_DISABLE": "1"})


def test_allows_when_the_vault_does_not_exist(tool_use, assert_allows, tmp_path):
    payload = tool_use(
        "Write", {"file_path": str(tmp_path / "x.md"), "content": "nothing here"}
    )

    assert_allows(HOOK, payload, env={"SECOND_BRAIN_VAULT": str(tmp_path / "missing")})


def test_allows_unrelated_tool(tool_use, assert_allows, vault, env):
    payload = tool_use("Read", {"file_path": note(vault, "wiki/concepts/Idea.md")})

    assert_allows(HOOK, payload, env=env)


def test_allows_payload_without_a_file_path(tool_use, assert_allows, vault, env):
    payload = tool_use("Write", {"content": GOOD})

    assert_allows(HOOK, payload, env=env)


def test_allows_frontmatter_with_a_yaml_list(tool_use, assert_allows, vault, env):
    content = GOOD.replace("tags: [concept]", "tags:\n  - concept\n  - idea")
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Listed.md"), "content": content}
    )

    assert_allows(HOOK, payload, env=env)


def test_blocks_wikilink_to_a_template(tool_use, assert_blocks, vault, env):
    (vault / "templates/entity.md").write_text("template body")
    content = GOOD + "\nSee [[entity]] for the shape.\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Shape.md"), "content": content}
    )

    assert_blocks(HOOK, payload, "KN004", env=env)


def test_allows_edit_of_a_note_that_does_not_exist_yet(tool_use, assert_allows, vault, env):
    payload = tool_use(
        "Edit",
        {
            "file_path": note(vault, "wiki/concepts/Absent.md"),
            "old_string": "a",
            "new_string": "b",
        },
    )

    assert_allows(HOOK, payload, env=env)


def test_caps_the_number_of_reported_findings(tool_use, assert_blocks, vault, env):
    noise = "\n".join(f"See [[Missing {index}]] here." for index in range(20))
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Noisy.md"), "content": GOOD + noise}
    )

    _code, stderr = assert_blocks(HOOK, payload, "KN004", env=env)

    assert "and 8 more" in stderr


def test_allows_a_command_with_unbalanced_quotes(tool_use, assert_allows, vault, env):
    payload = tool_use("Bash", {"command": "rm 'unterminated"})

    assert_allows(HOOK, payload, env=env)


def test_allows_removal_of_a_relative_path_outside_the_vault(tool_use, assert_allows, vault, env):
    payload = tool_use("Bash", {"command": "rm scratch-file.txt"})

    assert_allows(HOOK, payload, env=env)


def test_allows_malformed_stdin():
    import subprocess
    import sys

    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json at all",
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0


def test_skips_flag_tokens_in_a_removal(tool_use, assert_blocks, vault, env):
    target = vault / "wiki/concepts/Flagged.md"
    target.write_text(GOOD)
    payload = tool_use("Bash", {"command": f"rm -rf {target}"})

    assert_blocks(HOOK, payload, "KN006", env=env)


def test_exits_zero_on_undecodable_stdin(monkeypatch, vault):
    import importlib.util
    import io

    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
    spec = importlib.util.spec_from_file_location("knowledge_note_guard", hook)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault))
    monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    assert exit_info.value.code == 0

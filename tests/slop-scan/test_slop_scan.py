from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env
from _helpers.raising import raising

SCANNER = Path(__file__).resolve().parents[2] / "tools" / "slop-scan.py"
CLEAN = "# Retry budget\n\nThe worker retries three times, then dead-letters.\n"
SLOP = "# Notes\n\nThe scheduler plays a crucial role in the pipeline.\n"
NARRATION = "# Notes\n\nThe pinout was verified on 2026-10-11 against the board.\n"


def load_scanner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("slop_scan", SCANNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["slop_scan"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def scanner() -> ModuleType:
    return load_scanner()


def git(repo: Path, identity: tuple[str, str], *args: str) -> None:
    name, email = identity
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            f"user.name={name}",
            "-c",
            f"user.email={email}",
            *args,
        ],
        check=True,
        capture_output=True,
    )


def repo_with_commits(tmp_path: Path, faker: Faker, messages: list[str]) -> Path:
    identity = (faker.name(), faker.email())
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, identity, "init", "-q")
    for index, message in enumerate(messages):
        (repo / f"f{index}.txt").write_text(str(index), encoding="utf-8")
        git(repo, identity, "add", ".")
        git(repo, identity, "commit", "-q", "--no-verify", "-m", message)
    return repo


def test_clean_tree_exits_zero(scanner, tmp_path, capsys):
    # Arrange
    (tmp_path / "README.md").write_text(CLEAN, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(tmp_path)])

    # Assert
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "0 findings in 0 sources"


def test_slop_in_markdown_exits_one_and_names_the_code(scanner, tmp_path, capsys):
    # Arrange
    readme = tmp_path / "README.md"
    readme.write_text(SLOP, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(tmp_path)])

    # Assert
    out = capsys.readouterr().out
    assert exit_code == 1
    assert f"{readme}: SLOP002 significance inflation, line 3:" in out
    assert out.strip().endswith("1 findings in 1 sources")


def test_json_output_carries_every_field(scanner, tmp_path, capsys):
    # Arrange
    readme = tmp_path / "README.md"
    readme.write_text(SLOP, encoding="utf-8")

    # Act
    scanner.main([str(tmp_path), "--json"])

    # Assert
    rows = json.loads(capsys.readouterr().out)
    assert [(r["source"], r["code"]) for r in rows] == [(str(readme), "SLOP002")]
    assert rows[0]["location"].startswith("line 3:")


def test_dependency_directories_are_skipped(scanner, tmp_path, capsys):
    # Arrange
    vendored = tmp_path / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "README.md").write_text(SLOP, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(tmp_path)])

    # Assert
    assert exit_code == 0


def test_non_markdown_files_are_skipped(scanner, tmp_path):
    # Arrange
    (tmp_path / "notes.txt").write_text(SLOP, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(tmp_path)])

    # Assert
    assert exit_code == 0


def test_a_single_file_target_is_scanned(scanner, tmp_path, capsys):
    # Arrange
    doc = tmp_path / "guide.md"
    doc.write_text(SLOP, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(doc)])

    # Assert
    assert exit_code == 1
    assert f"{doc}: SLOP002" in capsys.readouterr().out


def test_search_narration_in_a_prompt_file_is_kept(scanner, tmp_path):
    # Arrange
    (tmp_path / "PROMPT.md").write_text(NARRATION, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(tmp_path)])

    # Assert
    assert exit_code == 0


def test_the_rule_catalogue_is_skipped(scanner, tmp_path):
    # Arrange
    rule = tmp_path / ".claude" / "rules" / "anti-slop.md"
    rule.parent.mkdir(parents=True)
    rule.write_text(SLOP, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(rule)])

    # Assert
    assert exit_code == 0


def test_the_rule_catalogue_is_skipped_by_relative_path(scanner, tmp_path, monkeypatch):
    # Arrange
    rule = tmp_path / ".claude" / "rules" / "anti-slop.md"
    rule.parent.mkdir(parents=True)
    rule.write_text(SLOP, encoding="utf-8")
    monkeypatch.chdir(tmp_path / ".claude")

    # Act
    exit_code = scanner.main(["rules/anti-slop.md"])

    # Assert
    assert exit_code == 0


def test_missing_path_exits_two(scanner, tmp_path, capsys):
    # Arrange
    missing = tmp_path / "absent"

    # Act
    exit_code = scanner.main([str(missing)])

    # Assert
    assert exit_code == 2
    assert f"slop-scan: no such path: {missing}" in capsys.readouterr().err


def test_too_many_files_exits_two(scanner, tmp_path, monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(scanner, "MAX_FILES", 1)
    (tmp_path / "a.md").write_text(CLEAN, encoding="utf-8")
    (tmp_path / "b.md").write_text(CLEAN, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(tmp_path)])

    # Assert
    assert exit_code == 2
    assert "more than 1 Markdown files" in capsys.readouterr().err


def test_a_slop_commit_message_is_reported(scanner, tmp_path, faker, capsys):
    # Arrange
    repo = repo_with_commits(
        tmp_path, faker, ["chore: start", "feat: add retries, highlighting the design"]
    )

    # Act
    exit_code = scanner.main([str(repo), "--commits", "HEAD~1..HEAD"])

    # Assert
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "SLOP003 participial evaluation tail" in out
    assert out.startswith("commit ")


def test_clean_commit_messages_exit_zero(scanner, tmp_path, faker):
    # Arrange
    repo = repo_with_commits(
        tmp_path, faker, ["chore: start", "feat: cap retries at three"]
    )

    # Act
    exit_code = scanner.main([str(repo), "--commits", "HEAD~1..HEAD"])

    # Assert
    assert exit_code == 0


def test_an_unknown_revision_range_exits_two(scanner, tmp_path, faker, capsys):
    # Arrange
    repo = repo_with_commits(tmp_path, faker, ["chore: start"])

    # Act
    exit_code = scanner.main([str(repo), "--commits", "nope..HEAD"])

    # Assert
    assert exit_code == 2
    assert "git log nope..HEAD failed" in capsys.readouterr().err


def test_git_that_cannot_start_exits_two(scanner, tmp_path, faker, monkeypatch, capsys):
    # Arrange
    repo = repo_with_commits(tmp_path, faker, ["chore: start"])
    monkeypatch.setattr(scanner.subprocess, "run", raising(OSError("git missing")))

    # Act
    exit_code = scanner.main([str(repo), "--commits", "HEAD"])

    # Assert
    assert exit_code == 2
    assert "git missing" in capsys.readouterr().err


def test_an_unloadable_detector_exits_two(scanner, tmp_path, monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(scanner, "HOOK_PATH", tmp_path / "absent.txt")

    # Act
    exit_code = scanner.main([str(tmp_path)])

    # Assert
    assert exit_code == 2
    assert "cannot load the detector" in capsys.readouterr().err


def test_the_script_runs_as_a_command(tmp_path):
    # Arrange
    (tmp_path / "README.md").write_text(SLOP, encoding="utf-8")

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCANNER), str(tmp_path)],
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stderr) == (1, "")


def test_a_file_target_scans_commits_of_its_repository(
    scanner, tmp_path, faker, capsys
):
    # Arrange
    repo = repo_with_commits(
        tmp_path, faker, ["chore: start", "feat: add retries, highlighting the design"]
    )
    doc = repo / "README.md"
    doc.write_text(CLEAN, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(doc), "--commits", "HEAD~1..HEAD"])

    # Assert
    assert (exit_code, "SLOP003" in capsys.readouterr().out) == (1, True)


def test_a_gitignored_markdown_file_is_not_scanned(scanner, tmp_path, faker):
    # Arrange
    repo = repo_with_commits(tmp_path, faker, ["chore: start"])
    (repo / ".gitignore").write_text("scratch/\n", encoding="utf-8")
    (repo / "scratch").mkdir()
    (repo / "scratch" / "notes.md").write_text(SLOP, encoding="utf-8")
    (repo / "README.md").write_text(CLEAN, encoding="utf-8")

    # Act
    exit_code = scanner.main([str(repo)])

    # Assert
    assert exit_code == 0


def test_git_log_without_git_raises_a_scan_error(scanner, tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv("PATH", str(tmp_path))

    # Act
    attempt = lambda: scanner.git_log(tmp_path, "HEAD")  # noqa: E731

    # Assert
    with pytest.raises(scanner.ScanError, match="git log HEAD failed"):
        attempt()

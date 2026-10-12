from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "hooks" / "vault-session-capture.py"
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402

VAULT_HEALTH = Path.home() / "second-brain" / ".ci" / "vault-health.py"


def load():
    spec = importlib.util.spec_from_file_location("vault_session_capture", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["vault_session_capture"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "daily").mkdir(parents=True)
    (root / "wiki" / "concepts").mkdir(parents=True)
    return root


@pytest.fixture
def project(tmp_path: Path, faker: Faker) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", faker.email()], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.name", faker.first_name()], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "chore: seed"], cwd=repo, check=True)
    return repo


def run(monkeypatch, vault_path, cwd, enabled: bool = True, stdin: str | None = None):
    module = load()
    if enabled:
        monkeypatch.setenv("VAULT_AUTO_CAPTURE", "1")
    else:
        monkeypatch.delenv("VAULT_AUTO_CAPTURE", raising=False)
    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(vault_path))
    payload = (
        stdin
        if stdin is not None
        else json.dumps(
            {
                "hook_event_name": "PreCompact",
                "cwd": str(cwd),
                "session_id": "abc123def456",
            }
        )
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return module.main()


def daily_note(vault: Path) -> Path:
    notes = list((vault / "daily").glob("*.md"))
    assert len(notes) == 1, notes
    return notes[0]


def load_vault_health():
    spec = importlib.util.spec_from_file_location("vh", VAULT_HEALTH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["vh"] = module
    spec.loader.exec_module(module)
    return module


def write_files(root: Path, count: int) -> None:
    for index in range(count):
        (root / f"file{index}.txt").write_text("x\n")


def test_is_inert_without_the_opt_in(monkeypatch, vault, project):
    # Arrange
    (project / "changed.txt").write_text("x\n")

    # Act
    code = run(monkeypatch, vault, project, enabled=False)

    # Assert
    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_creates_a_daily_note_when_work_happened(monkeypatch, vault, project):
    # Arrange
    (project / "changed.txt").write_text("x\n")

    # Act
    code = run(monkeypatch, vault, project)

    # Assert
    assert code == 0
    assert "changed.txt" in daily_note(vault).read_text()


def test_the_generated_note_carries_required_frontmatter(monkeypatch, vault, project):
    # Arrange
    (project / "changed.txt").write_text("x\n")

    # Act
    code = run(monkeypatch, vault, project)

    # Assert
    fields = kn.parse_frontmatter(daily_note(vault).read_text())
    assert code == 0
    assert fields is not None
    assert set(kn.REQUIRED_KEYS) - set(fields) == set()


def test_the_generated_note_carries_the_preamble(monkeypatch, vault, project):
    # Arrange
    (project / "changed.txt").write_text("x\n")

    # Act
    code = run(monkeypatch, vault, project)

    # Assert
    body = kn.body_after_frontmatter(daily_note(vault).read_text())
    assert code == 0
    assert kn.PREAMBLE in body


@pytest.mark.skipif(
    not VAULT_HEALTH.exists(), reason="vault linters not present on this machine"
)
def test_the_generated_note_passes_the_vault_linters(monkeypatch, vault, project):
    # Arrange
    (project / "changed.txt").write_text("x\n")
    vh = load_vault_health()

    # Act
    code = run(monkeypatch, vault, project)

    # Assert
    errors = [f for f in vh.audit(vault) if f.severity == "error"]
    assert code == 0
    assert errors == []


def test_the_note_marks_itself_as_machine_written(monkeypatch, vault, project):
    # Arrange
    (project / "changed.txt").write_text("x\n")

    # Act
    code = run(monkeypatch, vault, project)

    # Assert
    assert code == 0
    assert "Machine-written and unreviewed" in daily_note(vault).read_text()


def test_a_second_capture_appends_without_touching_the_first(
    monkeypatch, vault, project
):
    # Arrange
    (project / "first.txt").write_text("x\n")
    run(monkeypatch, vault, project)
    first = daily_note(vault).read_text()
    (project / "second.txt").write_text("y\n")

    # Act
    run(monkeypatch, vault, project)

    # Assert
    second = daily_note(vault).read_text()
    assert second.startswith(first) is True
    assert "first.txt" in second
    assert "second.txt" in second


def test_a_recent_commit_alone_is_worth_recording(monkeypatch, vault, project):
    # Arrange
    seed_subject = "chore: seed"

    # Act
    code = run(monkeypatch, vault, project)

    # Assert
    assert code == 0
    assert seed_subject in daily_note(vault).read_text()


def test_an_already_recorded_commit_is_not_repeated(monkeypatch, vault, project):
    # Arrange
    run(monkeypatch, vault, project)
    first = daily_note(vault).read_text()

    # Act
    run(monkeypatch, vault, project)

    # Assert
    assert daily_note(vault).read_text() == first


def test_nothing_is_written_when_there_is_no_new_work(monkeypatch, vault, tmp_path):
    # Arrange
    quiet = tmp_path / "quiet"
    quiet.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=quiet, check=True)

    # Act
    code = run(monkeypatch, vault, quiet)

    # Assert
    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_a_long_file_list_is_capped(monkeypatch, vault, project):
    # Arrange
    write_files(project, 80)

    # Act
    run(monkeypatch, vault, project)

    # Assert
    text = daily_note(vault).read_text()
    assert "- and 55 more file(s) not listed\n" in text
    assert len(text) < 8000


def test_it_writes_only_under_daily(monkeypatch, vault, project):
    # Arrange
    (project / "changed.txt").write_text("x\n")

    # Act
    run(monkeypatch, vault, project)

    # Assert
    written = {p.relative_to(vault).parts[0] for p in vault.rglob("*.md")}
    assert written == {"daily"}


def test_it_records_the_branch_and_project(monkeypatch, vault, project):
    # Arrange
    (project / "changed.txt").write_text("x\n")

    # Act
    run(monkeypatch, vault, project)

    # Assert
    assert "- Project: `project` on branch `main`\n" in daily_note(vault).read_text()


def test_it_is_silent_outside_a_repository(monkeypatch, vault, tmp_path):
    # Arrange
    loose = tmp_path / "loose"
    loose.mkdir()

    # Act
    code = run(monkeypatch, vault, loose)

    # Assert
    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_it_is_silent_when_the_vault_is_absent(monkeypatch, tmp_path, project):
    # Arrange
    (project / "changed.txt").write_text("x\n")

    # Act
    code = run(monkeypatch, tmp_path / "absent", project)

    # Assert
    assert code == 0


def test_malformed_stdin_is_tolerated(monkeypatch, vault, project):
    # Arrange
    stdin = "not json"

    # Act
    code = run(monkeypatch, vault, project, stdin=stdin)

    # Assert
    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_a_missing_cwd_is_tolerated(monkeypatch, vault, project):
    # Arrange
    stdin = json.dumps({"hook_event_name": "PreCompact"})

    # Act
    code = run(
        monkeypatch,
        vault,
        project,
        stdin=stdin,
    )

    # Assert
    assert code == 0


def test_it_exits_zero_when_the_daily_folder_is_missing(monkeypatch, tmp_path, project):
    # Arrange
    root = tmp_path / "bare-vault"
    root.mkdir()
    (project / "changed.txt").write_text("x\n")

    # Act
    code = run(monkeypatch, root, project)

    # Assert
    assert code == 0
    assert (root / "daily").is_dir() is True


def test_a_nonexistent_cwd_is_tolerated(monkeypatch, vault, tmp_path):
    # Arrange
    cwd = tmp_path / "gone"

    # Act
    code = run(monkeypatch, vault, cwd)

    # Assert
    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_a_rename_records_only_the_destination(monkeypatch, vault, project):
    # Arrange
    subprocess.run(["git", "mv", "seed.txt", "renamed.txt"], cwd=project, check=True)

    # Act
    run(monkeypatch, vault, project)

    # Assert
    assert "- Touched: `renamed.txt`\n" in daily_note(vault).read_text()


def git_in(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        },
    )


@pytest.fixture
def repo_with_an_unstaged_edit(tmp_path: Path, faker: Faker) -> Path:
    root = tmp_path / "work"
    root.mkdir()
    git_in(root, "init", "-q", "-b", "main")
    git_in(root, "config", "user.email", faker.email())
    git_in(root, "config", "user.name", faker.first_name())
    git_in(root, "config", "commit.gpgsign", "false")
    (root / "hooks").mkdir()
    (root / "hooks" / "recall.py").write_text("x = 1\n", encoding="utf-8")
    (root / "keep.md").write_text("a\n", encoding="utf-8")
    git_in(root, "add", ".")
    git_in(root, "commit", "-qm", "init")
    (root / "hooks" / "recall.py").write_text("x = 2\n", encoding="utf-8")
    return root


def test_an_unstaged_path_keeps_its_first_character(repo_with_an_unstaged_edit):
    # Arrange
    module = load()

    # Act
    names = module.changed_files(repo_with_an_unstaged_edit)

    # Assert
    assert names == ["hooks/recall.py"]


def test_a_staged_path_keeps_its_first_character(repo_with_an_unstaged_edit):
    # Arrange
    git_in(repo_with_an_unstaged_edit, "add", "hooks/recall.py")
    module = load()

    # Act
    names = module.changed_files(repo_with_an_unstaged_edit)

    # Assert
    assert names == ["hooks/recall.py"]


def test_an_untracked_path_keeps_its_first_character(repo_with_an_unstaged_edit):
    # Arrange
    (repo_with_an_unstaged_edit / "notes.md").write_text("n\n", encoding="utf-8")
    module = load()

    # Act
    names = module.changed_files(repo_with_an_unstaged_edit)

    # Assert
    assert "notes.md" in names
    assert "hooks/recall.py" in names

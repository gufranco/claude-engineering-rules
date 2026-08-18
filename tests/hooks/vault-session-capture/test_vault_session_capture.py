"""Coverage for the opt-in automatic session capture.

The hook writes through Python rather than the Write tool, so the write-time
guard never sees its output. These tests carry that weight instead: the
generated note must satisfy the same specification a hand-written one does.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "hooks" / "vault-session-capture.py"
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402


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
def project(tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
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


def test_is_inert_without_the_opt_in(monkeypatch, vault, project):
    (project / "changed.txt").write_text("x\n")

    code = run(monkeypatch, vault, project, enabled=False)

    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_creates_a_daily_note_when_work_happened(monkeypatch, vault, project):
    (project / "changed.txt").write_text("x\n")

    code = run(monkeypatch, vault, project)

    assert code == 0
    assert "changed.txt" in daily_note(vault).read_text()


def test_the_generated_note_carries_required_frontmatter(monkeypatch, vault, project):
    (project / "changed.txt").write_text("x\n")

    run(monkeypatch, vault, project)

    fields = kn.parse_frontmatter(daily_note(vault).read_text())
    assert fields is not None
    assert all(key in fields for key in kn.REQUIRED_KEYS)


def test_the_generated_note_carries_the_preamble(monkeypatch, vault, project):
    (project / "changed.txt").write_text("x\n")

    run(monkeypatch, vault, project)

    body = kn.body_after_frontmatter(daily_note(vault).read_text())
    assert kn.PREAMBLE in body


def test_the_generated_note_passes_the_vault_linters(monkeypatch, vault, project):
    (project / "changed.txt").write_text("x\n")
    run(monkeypatch, vault, project)

    spec = importlib.util.spec_from_file_location(
        "vh", Path.home() / "second-brain" / ".ci" / "vault-health.py"
    )
    if (
        spec is None
        or not (Path.home() / "second-brain" / ".ci" / "vault-health.py").exists()
    ):
        pytest.skip("vault linters not present on this machine")
    vh = importlib.util.module_from_spec(spec)
    sys.modules["vh"] = vh
    spec.loader.exec_module(vh)

    errors = [f for f in vh.audit(vault) if f.severity == "error"]

    assert errors == []


def test_the_note_marks_itself_as_machine_written(monkeypatch, vault, project):
    (project / "changed.txt").write_text("x\n")

    run(monkeypatch, vault, project)

    text = daily_note(vault).read_text().lower()
    assert "machine-written" in text or "automatic capture" in text


def test_a_second_capture_appends_without_touching_the_first(
    monkeypatch, vault, project
):
    (project / "first.txt").write_text("x\n")
    run(monkeypatch, vault, project)
    first = daily_note(vault).read_text()

    (project / "second.txt").write_text("y\n")
    run(monkeypatch, vault, project)
    second = daily_note(vault).read_text()

    assert second.startswith(first)
    assert "first.txt" in second
    assert "second.txt" in second


def test_a_recent_commit_alone_is_worth_recording(monkeypatch, vault, project):
    code = run(monkeypatch, vault, project)

    assert code == 0
    assert "chore: seed" in daily_note(vault).read_text()


def test_an_already_recorded_commit_is_not_repeated(monkeypatch, vault, project):
    run(monkeypatch, vault, project)
    first = daily_note(vault).read_text()

    run(monkeypatch, vault, project)

    assert daily_note(vault).read_text() == first


def test_nothing_is_written_when_there_is_no_new_work(monkeypatch, vault, tmp_path):
    quiet = tmp_path / "quiet"
    quiet.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=quiet, check=True)

    code = run(monkeypatch, vault, quiet)

    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_a_long_file_list_is_capped(monkeypatch, vault, project):
    for index in range(80):
        (project / f"file{index}.txt").write_text("x\n")

    run(monkeypatch, vault, project)

    text = daily_note(vault).read_text()
    assert "more" in text
    assert len(text) < 8000


def test_it_writes_only_under_daily(monkeypatch, vault, project):
    (project / "changed.txt").write_text("x\n")

    run(monkeypatch, vault, project)

    written = {p.relative_to(vault).parts[0] for p in vault.rglob("*.md")}
    assert written == {"daily"}


def test_it_records_the_branch_and_project(monkeypatch, vault, project):
    (project / "changed.txt").write_text("x\n")

    run(monkeypatch, vault, project)

    text = daily_note(vault).read_text()
    assert "project" in text.lower()
    assert "main" in text


def test_it_is_silent_outside_a_repository(monkeypatch, vault, tmp_path):
    loose = tmp_path / "loose"
    loose.mkdir()

    code = run(monkeypatch, vault, loose)

    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_it_is_silent_when_the_vault_is_absent(monkeypatch, tmp_path, project):
    (project / "changed.txt").write_text("x\n")

    code = run(monkeypatch, tmp_path / "absent", project)

    assert code == 0


def test_malformed_stdin_is_tolerated(monkeypatch, vault, project):
    code = run(monkeypatch, vault, project, stdin="not json")

    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_a_missing_cwd_is_tolerated(monkeypatch, vault, project):
    code = run(
        monkeypatch,
        vault,
        project,
        stdin=json.dumps({"hook_event_name": "PreCompact"}),
    )

    assert code == 0


def test_it_exits_zero_when_the_daily_folder_is_missing(monkeypatch, tmp_path, project):
    root = tmp_path / "bare-vault"
    root.mkdir()
    (project / "changed.txt").write_text("x\n")

    code = run(monkeypatch, root, project)

    assert code == 0
    assert (root / "daily").is_dir()


def test_a_nonexistent_cwd_is_tolerated(monkeypatch, vault, tmp_path):
    code = run(monkeypatch, vault, tmp_path / "gone")

    assert code == 0
    assert list((vault / "daily").glob("*.md")) == []


def test_a_rename_records_only_the_destination(monkeypatch, vault, project):
    subprocess.run(["git", "mv", "seed.txt", "renamed.txt"], cwd=project, check=True)

    run(monkeypatch, vault, project)

    text = daily_note(vault).read_text()
    assert "renamed.txt" in text

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "session-mine.py"
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402

VAULT_HEALTH = Path.home() / "second-brain" / ".ci" / "vault-health.py"


def load_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load() -> ModuleType:
    return load_path("session_mine", SCRIPT)


def record(**fields: object) -> str:
    return json.dumps(fields)


def load_vault_health() -> ModuleType:
    return load_path("vh_mine", VAULT_HEALTH)


def write_titled_transcripts_sharing_a_basename(
    root: Path, count: int, faker: Faker
) -> None:
    for index in range(count):
        d = root / f"-x-{index}-shared"
        d.mkdir(parents=True)
        (d / "s.jsonl").write_text(
            record(type="ai-title", aiTitle=faker.sentence(), sessionId=faker.uuid4())
            + "\n"
        )


def _first_session_lines() -> list[str]:
    return [
        record(
            type="user",
            cwd="/Users/someone/work/widget",
            gitBranch="main",
            timestamp="2026-05-01T10:00:00Z",
            sessionId="s1",
        ),
        record(type="ai-title", aiTitle="Fix the widget parser", sessionId="s1"),
        record(
            type="assistant",
            cwd="/Users/someone/work/widget",
            gitBranch="main",
            timestamp="2026-05-01T11:00:00Z",
            sessionId="s1",
        ),
    ]


def _second_session_lines() -> list[str]:
    return [
        record(
            type="user",
            cwd="/Users/someone/work/widget",
            gitBranch="feature/x",
            timestamp="2026-06-15T09:00:00Z",
            sessionId="s2",
        ),
        record(
            type="ai-title",
            aiTitle="Add retries to the widget client",
            sessionId="s2",
        ),
        "not valid json",
    ]


@pytest.fixture
def projects(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    d = root / "-Users-someone-work-widget"
    d.mkdir(parents=True)
    (d / "s1.jsonl").write_text("\n".join(_first_session_lines()) + "\n")
    (d / "s2.jsonl").write_text("\n".join(_second_session_lines()) + "\n")
    return root


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "wiki" / "projects").mkdir(parents=True)
    return root


def test_scan_groups_by_project(projects):
    # Arrange
    module = load()

    # Act
    found = module.scan(projects)

    # Assert
    assert list(found) == ["-Users-someone-work-widget"]


def test_scan_collects_titles_sessions_and_branches(projects):
    # Arrange
    module = load()

    # Act
    summary = module.scan(projects)["-Users-someone-work-widget"]

    # Assert
    assert summary.sessions == 2
    assert summary.titles == [
        "Add retries to the widget client",
        "Fix the widget parser",
    ]
    assert summary.branches == ["feature/x", "main"]
    assert summary.name == "widget"


def test_scan_records_the_date_range(projects):
    # Arrange
    module = load()

    # Act
    summary = module.scan(projects)["-Users-someone-work-widget"]

    # Assert
    assert summary.first == "2026-05-01"
    assert summary.last == "2026-06-15"


def test_scan_tolerates_malformed_lines(projects):
    # Arrange
    module = load()

    # Act
    summary = module.scan(projects)["-Users-someone-work-widget"]

    # Assert
    assert summary.sessions == 2


def test_scan_ignores_a_directory_with_no_transcripts(tmp_path):
    # Arrange
    module = load()
    (tmp_path / "projects" / "empty").mkdir(parents=True)

    # Act
    result = module.scan(tmp_path / "projects")

    # Assert
    assert result == {}


def test_render_carries_required_frontmatter(projects):
    # Arrange
    module = load()
    summary = module.scan(projects)["-Users-someone-work-widget"]

    # Act
    text = module.render(summary)

    # Assert
    fields = kn.parse_frontmatter(text)
    assert fields is not None
    assert set(kn.REQUIRED_KEYS) - set(fields) == set()
    assert fields["type"] == "project"


def test_render_carries_the_preamble_and_states_its_coverage(projects):
    # Arrange
    module = load()
    summary = module.scan(projects)["-Users-someone-work-widget"]

    # Act
    text = module.render(summary)

    # Assert
    body = kn.body_after_frontmatter(text)
    assert kn.PREAMBLE in body
    assert "metadata" in body.lower()


def test_render_stamps_every_count(projects):
    # Arrange
    module = load()
    summary = module.scan(projects)["-Users-someone-work-widget"]

    # Act
    text = module.render(summary)

    # Assert
    undated_volatile = [
        line
        for _number, line, dated in kn.walk_lines(kn.body_after_frontmatter(text))
        if not dated and kn.is_volatile_claim(line)
    ]
    assert undated_volatile == []


def test_render_lists_the_titles(projects):
    # Arrange
    module = load()
    summary = module.scan(projects)["-Users-someone-work-widget"]

    # Act
    text = module.render(summary)

    # Assert
    assert "Fix the widget parser" in text


def test_apply_writes_one_note_per_project(projects, vault):
    # Arrange
    module = load()

    # Act
    written = module.apply(module.scan(projects), vault, dry_run=False)

    # Assert
    assert written == ["wiki/projects/widget.md"]
    assert (vault / "wiki" / "projects" / "widget.md").is_file() is True


def test_dry_run_writes_nothing(projects, vault):
    # Arrange
    module = load()

    # Act
    written = module.apply(module.scan(projects), vault, dry_run=True)

    # Assert
    assert written == ["wiki/projects/widget.md"]
    assert (vault / "wiki" / "projects" / "widget.md").exists() is False


def test_apply_never_overwrites_an_existing_note(projects, vault, faker: Faker):
    # Arrange
    module = load()
    target = vault / "wiki" / "projects" / "widget.md"
    hand_written = f"{faker.paragraph()}\n"
    target.write_text(hand_written)

    # Act
    written = module.apply(module.scan(projects), vault, dry_run=False)

    # Assert
    assert written == []
    assert target.read_text() == hand_written


@pytest.mark.skipif(
    not VAULT_HEALTH.exists(),
    reason=f"external vault linter {VAULT_HEALTH} is not installed on this machine",
)
def test_generated_notes_pass_the_structural_linter(projects, vault):
    # Arrange
    module = load()
    vh = load_vault_health()

    # Act
    written = module.apply(module.scan(projects), vault, dry_run=False)

    # Assert
    errors = [f for f in vh.audit(vault) if f.severity == "error"]
    assert written == ["wiki/projects/widget.md"]
    assert errors == []


def test_main_reports_without_applying(projects, vault, capsys):
    # Arrange
    module = load()

    # Act
    code = module.main(["--projects", str(projects), "--path", str(vault)])

    # Assert
    assert code == 0
    assert "widget" in capsys.readouterr().out
    assert (vault / "wiki" / "projects" / "widget.md").exists() is False


def test_main_applies_when_asked(projects, vault):
    # Arrange
    module = load()

    # Act
    code = module.main(["--projects", str(projects), "--path", str(vault), "--apply"])

    # Assert
    assert code == 0
    assert (vault / "wiki" / "projects" / "widget.md").is_file() is True


def test_main_emits_json(projects, vault, capsys):
    # Arrange
    module = load()

    # Act
    module.main(["--projects", str(projects), "--path", str(vault), "--json"])

    # Assert
    payload = json.loads(capsys.readouterr().out)
    assert payload["projects"] == 1


def test_main_errors_without_a_vault(projects, tmp_path, capsys):
    # Arrange
    module = load()

    # Act
    code = module.main(
        ["--projects", str(projects), "--path", str(tmp_path / "absent")]
    )

    # Assert
    assert code == 2
    assert "not a directory" in capsys.readouterr().err.lower()


def test_main_errors_without_a_projects_directory(vault, tmp_path, capsys):
    # Arrange
    module = load()

    # Act
    code = module.main(["--projects", str(tmp_path / "absent"), "--path", str(vault)])

    # Assert
    assert code == 2
    assert "transcript" in capsys.readouterr().err.lower()


def test_a_project_without_a_recorded_cwd_falls_back_to_the_directory_name(
    tmp_path, faker: Faker
):
    # Arrange
    module = load()
    root = tmp_path / "projects"
    d = root / "-Users-someone-orphan"
    d.mkdir(parents=True)
    (d / "s.jsonl").write_text(
        record(type="ai-title", aiTitle=faker.sentence(), sessionId=faker.uuid4())
        + "\n"
    )

    # Act
    summary = module.scan(root)["-Users-someone-orphan"]

    # Assert
    assert summary.name == "orphan"
    assert summary.first == ""


def test_a_project_without_titles_says_so(tmp_path):
    # Arrange
    module = load()
    root = tmp_path / "projects"
    d = root / "-Users-someone-quiet"
    d.mkdir(parents=True)
    (d / "s.jsonl").write_text(
        record(
            type="user", cwd="/Users/someone/quiet", timestamp="2026-05-01T10:00:00Z"
        )
        + "\n"
    )

    # Act
    text = module.render(module.scan(root)["-Users-someone-quiet"])

    # Assert
    assert "TBD" in text
    assert "No session titles" in text


def test_a_long_title_list_is_capped(tmp_path, faker: Faker):
    # Arrange
    module = load()
    root = tmp_path / "projects"
    d = root / "-Users-someone-busy"
    d.mkdir(parents=True)
    header = [
        record(type="user", cwd="/Users/someone/busy", timestamp="2026-05-01T10:00:00Z")
    ]
    titles = [
        record(type="ai-title", aiTitle=f"{faker.sentence()} {i}", sessionId=f"s{i}")
        for i in range(60)
    ]
    lines = [*header, *titles]
    (d / "s.jsonl").write_text("\n".join(lines) + "\n")

    # Act
    text = module.render(module.scan(root)["-Users-someone-busy"])

    # Assert
    assert "more not listed" in text


def two_projects(tmp_path: Path, cwd_a: str, cwd_b: str) -> Path:
    root = tmp_path / "projects"
    for index, cwd in enumerate((cwd_a, cwd_b)):
        d = root / f"-dir-{index}"
        d.mkdir(parents=True)
        (d / "s.jsonl").write_text(
            record(type="user", cwd=cwd, timestamp="2026-05-01T10:00:00Z") + "\n"
        )
    return root


def test_two_projects_with_the_same_basename_get_distinct_notes(tmp_path, vault):
    # Arrange
    module = load()
    root = two_projects(
        tmp_path, "/Users/someone/.claude", "/Users/someone/work/.claude"
    )

    # Act
    written = module.apply(module.scan(root), vault, dry_run=False)

    # Assert
    assert written == ["wiki/projects/claude.md", "wiki/projects/work .claude.md"]


def test_a_leading_dot_is_stripped_from_the_note_name(tmp_path, vault):
    # Arrange
    module = load()
    root = two_projects(tmp_path, "/Users/someone/.dotfiles", "/Users/someone/other")

    # Act
    written = module.apply(module.scan(root), vault, dry_run=False)

    # Assert
    assert written == ["wiki/projects/dotfiles.md", "wiki/projects/other.md"]


def test_collision_falls_back_to_a_numeric_suffix_without_a_cwd(
    tmp_path, vault, faker: Faker
):
    # Arrange
    module = load()
    root = tmp_path / "projects"
    write_titled_transcripts_sharing_a_basename(root, 2, faker)

    # Act
    written = module.apply(module.scan(root), vault, dry_run=False)

    # Assert
    assert written == ["wiki/projects/shared.md", "wiki/projects/shared 2.md"]

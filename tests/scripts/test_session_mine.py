"""Coverage for the session miner.

It turns Claude Code transcript metadata into vault notes. Everything it writes
is observed from the record, never inferred from conversation bodies, and the
generated notes must satisfy the same specification a hand-written note does.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "session-mine.py"
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402


def load():
    spec = importlib.util.spec_from_file_location("session_mine", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["session_mine"] = module
    spec.loader.exec_module(module)
    return module


def record(**fields) -> str:
    return json.dumps(fields)


@pytest.fixture
def projects(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    d = root / "-Users-someone-work-widget"
    d.mkdir(parents=True)
    (d / "s1.jsonl").write_text(
        "\n".join(
            [
                record(
                    type="user",
                    cwd="/Users/someone/work/widget",
                    gitBranch="main",
                    timestamp="2026-05-01T10:00:00Z",
                    sessionId="s1",
                ),
                record(
                    type="ai-title", aiTitle="Fix the widget parser", sessionId="s1"
                ),
                record(
                    type="assistant",
                    cwd="/Users/someone/work/widget",
                    gitBranch="main",
                    timestamp="2026-05-01T11:00:00Z",
                    sessionId="s1",
                ),
            ]
        )
        + "\n"
    )
    (d / "s2.jsonl").write_text(
        "\n".join(
            [
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
        )
        + "\n"
    )
    return root


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "wiki" / "projects").mkdir(parents=True)
    return root


def test_scan_groups_by_project(projects):
    module = load()

    found = module.scan(projects)

    assert list(found) == ["-Users-someone-work-widget"]


def test_scan_collects_titles_sessions_and_branches(projects):
    module = load()

    summary = module.scan(projects)["-Users-someone-work-widget"]

    assert summary.sessions == 2
    assert summary.titles == [
        "Add retries to the widget client",
        "Fix the widget parser",
    ]
    assert summary.branches == ["feature/x", "main"]
    assert summary.name == "widget"


def test_scan_records_the_date_range(projects):
    module = load()

    summary = module.scan(projects)["-Users-someone-work-widget"]

    assert summary.first == "2026-05-01"
    assert summary.last == "2026-06-15"


def test_scan_tolerates_malformed_lines(projects):
    module = load()

    summary = module.scan(projects)["-Users-someone-work-widget"]

    assert summary.sessions == 2


def test_scan_ignores_a_directory_with_no_transcripts(tmp_path):
    module = load()
    (tmp_path / "projects" / "empty").mkdir(parents=True)

    assert module.scan(tmp_path / "projects") == {}


def test_render_carries_required_frontmatter(projects):
    module = load()
    summary = module.scan(projects)["-Users-someone-work-widget"]

    text = module.render(summary)

    fields = kn.parse_frontmatter(text)
    assert fields is not None
    assert all(key in fields for key in kn.REQUIRED_KEYS)
    assert fields["type"] == "project"


def test_render_carries_the_preamble_and_states_its_coverage(projects):
    module = load()
    summary = module.scan(projects)["-Users-someone-work-widget"]

    text = module.render(summary)

    body = kn.body_after_frontmatter(text)
    assert kn.PREAMBLE in body
    assert "metadata" in body.lower()


def test_render_stamps_every_count(projects):
    module = load()
    summary = module.scan(projects)["-Users-someone-work-widget"]

    text = module.render(summary)

    body = kn.body_after_frontmatter(text)
    for _number, line, dated in kn.walk_lines(body):
        if not dated:
            assert not kn.is_volatile_claim(line), line


def test_render_lists_the_titles(projects):
    module = load()
    summary = module.scan(projects)["-Users-someone-work-widget"]

    text = module.render(summary)

    assert "Fix the widget parser" in text


def test_apply_writes_one_note_per_project(projects, vault):
    module = load()

    written = module.apply(module.scan(projects), vault, dry_run=False)

    assert written == ["wiki/projects/widget.md"]
    assert (vault / "wiki" / "projects" / "widget.md").is_file()


def test_dry_run_writes_nothing(projects, vault):
    module = load()

    written = module.apply(module.scan(projects), vault, dry_run=True)

    assert written == ["wiki/projects/widget.md"]
    assert not (vault / "wiki" / "projects" / "widget.md").exists()


def test_apply_never_overwrites_an_existing_note(projects, vault):
    module = load()
    target = vault / "wiki" / "projects" / "widget.md"
    target.write_text("hand written\n")

    written = module.apply(module.scan(projects), vault, dry_run=False)

    assert written == []
    assert target.read_text() == "hand written\n"


def test_generated_notes_pass_the_structural_linter(projects, vault):
    module = load()
    module.apply(module.scan(projects), vault, dry_run=False)
    linter = Path.home() / "second-brain" / ".ci" / "vault-health.py"
    if not linter.exists():
        pytest.skip("vault linters not present on this machine")
    spec = importlib.util.spec_from_file_location("vh_mine", linter)
    vh = importlib.util.module_from_spec(spec)
    sys.modules["vh_mine"] = vh
    spec.loader.exec_module(vh)

    errors = [f for f in vh.audit(vault) if f.severity == "error"]

    assert errors == []


def test_main_reports_without_applying(projects, vault, capsys):
    module = load()

    code = module.main(["--projects", str(projects), "--path", str(vault)])

    assert code == 0
    assert "widget" in capsys.readouterr().out
    assert not (vault / "wiki" / "projects" / "widget.md").exists()


def test_main_applies_when_asked(projects, vault):
    module = load()

    code = module.main(["--projects", str(projects), "--path", str(vault), "--apply"])

    assert code == 0
    assert (vault / "wiki" / "projects" / "widget.md").is_file()


def test_main_emits_json(projects, vault, capsys):
    module = load()

    module.main(["--projects", str(projects), "--path", str(vault), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["projects"] == 1


def test_main_errors_without_a_vault(projects, tmp_path, capsys):
    module = load()

    code = module.main(
        ["--projects", str(projects), "--path", str(tmp_path / "absent")]
    )

    assert code == 2
    assert "not a directory" in capsys.readouterr().err.lower()


def test_main_errors_without_a_projects_directory(vault, tmp_path, capsys):
    module = load()

    code = module.main(["--projects", str(tmp_path / "absent"), "--path", str(vault)])

    assert code == 2
    assert "transcript" in capsys.readouterr().err.lower()


def test_a_project_without_a_recorded_cwd_falls_back_to_the_directory_name(
    tmp_path, vault
):
    module = load()
    root = tmp_path / "projects"
    d = root / "-Users-someone-orphan"
    d.mkdir(parents=True)
    (d / "s.jsonl").write_text(
        record(type="ai-title", aiTitle="Something", sessionId="s") + "\n"
    )

    summary = module.scan(root)["-Users-someone-orphan"]

    assert summary.name == "orphan"
    assert summary.first == ""


def test_a_project_without_titles_says_so(tmp_path, vault):
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

    text = module.render(module.scan(root)["-Users-someone-quiet"])

    assert "TBD" in text
    assert "No session titles" in text


def test_a_long_title_list_is_capped(tmp_path):
    module = load()
    root = tmp_path / "projects"
    d = root / "-Users-someone-busy"
    d.mkdir(parents=True)
    lines = [
        record(type="user", cwd="/Users/someone/busy", timestamp="2026-05-01T10:00:00Z")
    ]
    lines += [
        record(type="ai-title", aiTitle=f"Task number {i}", sessionId=f"s{i}")
        for i in range(60)
    ]
    (d / "s.jsonl").write_text("\n".join(lines) + "\n")

    text = module.render(module.scan(root)["-Users-someone-busy"])

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
    module = load()
    root = two_projects(
        tmp_path, "/Users/someone/.claude", "/Users/someone/work/.claude"
    )

    written = module.apply(module.scan(root), vault, dry_run=False)

    assert len(written) == 2
    assert len(set(written)) == 2


def test_a_leading_dot_is_stripped_from_the_note_name(tmp_path, vault):
    module = load()
    root = two_projects(tmp_path, "/Users/someone/.dotfiles", "/Users/someone/other")

    written = module.apply(module.scan(root), vault, dry_run=False)

    assert not any(Path(w).name.startswith(".") for w in written)


def test_collision_falls_back_to_a_numeric_suffix_without_a_cwd(tmp_path, vault):
    module = load()
    root = tmp_path / "projects"
    for index in range(2):
        d = root / f"-x-{index}-shared"
        d.mkdir(parents=True)
        (d / "s.jsonl").write_text(
            record(type="ai-title", aiTitle="t", sessionId="s") + "\n"
        )

    written = module.apply(module.scan(root), vault, dry_run=False)

    assert written == ["wiki/projects/shared.md", "wiki/projects/shared 2.md"]

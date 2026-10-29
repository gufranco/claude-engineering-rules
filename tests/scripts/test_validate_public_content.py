from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-public-content.py"


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_public_content", SCRIPT)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, loaded)
    spec.loader.exec_module(loaded)
    return loaded


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("# Rule\n\n## Provenance\n\nAdded once.\n", "provenance heading"),
        ("Decided 2026-10-14. The guard blocks.\n", "dated change"),
        ("Verified against the text on 2026-05-27.\n", "dated change"),
        ("This changed by direct user instruction.\n", "attribution"),
        ("Adopted on owner request from a course.\n", "attribution"),
        (
            "Folded in after acme/web #677 was opened.\n",
            "cross-repository pull request",
        ),
    ],
)
def test_reports_history_in_prose(
    module: ModuleType, tmp_path: Path, text: str, kind: str
) -> None:
    # Arrange
    _write(tmp_path, "standards/example.md", text)

    # Act
    findings = module.findings(tmp_path)

    # Assert
    assert [finding.kind for finding in findings] == [kind]


def test_ignores_code_spans_fences_and_release_headings(
    module: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    date = faker.date(pattern="%Y-%m-%d")
    _write(
        tmp_path,
        "standards/example.md",
        f"Use `Decided {date}` as a sample.\n\n```text\n## Provenance\nAdded {date}\n```\n",
    )
    _write(
        tmp_path,
        "CHANGELOG.md",
        f"## {date}\n\n### Added\n\n- A hook that blocks a forced push.\n",
    )
    _write(
        tmp_path,
        "standards/dates.md",
        f"The act took effect {date}, and `{faker.word()}` is a word.\n",
    )

    # Act
    findings = module.findings(tmp_path)

    # Assert
    assert findings == []


def test_reports_attribution_in_the_changelog(
    module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    _write(
        tmp_path,
        "CHANGELOG.md",
        "## 1.0.0\n\n- Added a hook by direct user instruction\n",
    )

    # Act
    findings = module.findings(tmp_path)

    # Assert
    assert [(finding.path, finding.kind) for finding in findings] == [
        ("CHANGELOG.md", "attribution")
    ]


def test_main_checks_this_repository(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _write(tmp_path, "README.md", "The rule holds.\n")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    # Act
    code = module.main()

    # Assert
    assert code == 0


def test_lists_only_tracked_markdown_in_a_git_repository(
    module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=30)
    _write(tmp_path, "tracked.md", "Decided 2026-10-14.\n")
    _write(tmp_path, "untracked.md", "Decided 2026-10-14.\n")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "tracked.md"], check=True, timeout=30
    )

    # Act
    findings = module.findings(tmp_path)

    # Assert
    assert [finding.path for finding in findings] == ["tracked.md"]


def test_main_fails_with_a_report_and_passes_when_clean(
    module: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _write(tmp_path, "a.md", "Promoted 2026-08-26 after recurrences.\n")
    dirty = module.check(tmp_path)
    (tmp_path / "a.md").write_text("The rule holds.\n", encoding="utf-8")

    # Act
    clean = module.check(tmp_path)

    # Assert
    out = capsys.readouterr().out
    assert (dirty, clean) == (1, 0)
    assert "a.md:1: dated change" in out
    assert "PASSED" in out


def test_an_unreadable_file_fails_the_check(module: ModuleType, tmp_path: Path) -> None:
    # Arrange
    (tmp_path / "broken.md").write_bytes(b"# Title\n\xff\xfe not utf-8\n")

    # Act
    findings = module.findings(tmp_path)

    # Assert
    assert [(finding.path, finding.kind) for finding in findings] == [
        ("broken.md", "unreadable")
    ]


def test_the_script_passes_on_this_repository() -> None:
    # Arrange
    env = apply_coverage_env(dict(os.environ))

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # Assert
    assert proc.returncode == 0, proc.stdout

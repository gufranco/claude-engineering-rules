from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

HOOKS_DIR = Path(__file__).resolve().parents[3] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import assertion_weakening  # noqa: E402
from _lib.assertion_weakening import (  # noqa: E402
    UNREADABLE,
    findings_for,
    weakening_findings,
)

fake = Faker()
Faker.seed(20261027)


def test_removed_expect_is_reported_as_an_assertion_drop() -> None:
    # Arrange
    before = "expect(total).toBe(1550);\nexpect(count).toBe(2);\n"
    after = "expect(total).toBe(1550);\n"

    # Act
    findings = weakening_findings(before, after)

    # Assert
    assert findings == ["assertions drop from 2 to 1"]


def test_replacing_an_assertion_with_a_stricter_one_is_allowed() -> None:
    # Arrange
    before = "expect(result).toBeTruthy();\n"
    after = "expect(result).toEqual({ status: 'COMPLETED' });\n"

    # Act
    findings = weakening_findings(before, after)

    # Assert
    assert findings == []


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("assert total == 5\n", "total\n"),
        ("self.assertEqual(a, 5)\n", "a\n"),
        ("assert_eq!(a, 5);\n", "a;\n"),
        ("assert.Equal(t, 5, a)\n", "_ = a\n"),
        ('t.Fatalf("got %d", a)\n', "_ = a\n"),
        ("XCTAssertEqual(a, 5)\n", "_ = a\n"),
        ("with pytest.raises(ValueError):\n", "if True:\n"),
    ],
)
def test_each_language_assertion_form_is_counted(before: str, after: str) -> None:
    # Arrange
    removed = (before, after)

    # Act
    findings = weakening_findings(*removed)

    # Assert
    assert findings == ["assertions drop from 1 to 0"]


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("def test_total():\n    pass\n", "def total():\n    pass\n"),
        ("func TestTotal(t *testing.T) {}\n", "func total() {}\n"),
        ("it('totals', () => {});\n", "const totals = () => {};\n"),
        ("#[test]\nfn totals() {}\n", "fn totals() {}\n"),
    ],
)
def test_a_deleted_test_case_is_reported(before: str, after: str) -> None:
    # Arrange
    removed = (before, after)

    # Act
    findings = weakening_findings(*removed)

    # Assert
    assert findings == ["test cases drop from 1 to 0"]


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("it('totals', f);\n", "it.skip('totals', f);\n"),
        ("it('totals', f);\n", "xit('totals', f);\n"),
        ("def test_x():\n", "@pytest.mark.skip\ndef test_x():\n"),
        ("func TestX(t *testing.T) {\n", "func TestX(t *testing.T) {\n\tt.Skip()\n"),
        ("#[test]\nfn x() {}\n", "#[test]\n#[ignore]\nfn x() {}\n"),
    ],
)
def test_an_added_skip_marker_is_reported(before: str, after: str) -> None:
    # Arrange
    skipped = (before, after)

    # Act
    findings = weakening_findings(*skipped)

    # Assert
    assert "skip markers rise from 0 to 1" in findings


def test_a_skip_marker_inside_a_string_literal_is_not_counted() -> None:
    # Arrange
    before = 'payload = {"new_string": "x"}\n'
    after = 'payload = {"new_string": "it.skip(\'totals\', f)"}\n'

    # Act
    findings = weakening_findings(before, after)

    # Assert
    assert findings == []


def test_edit_compares_old_and_new_strings() -> None:
    # Arrange
    tool_input = {
        "file_path": f"/repo/tests/test_{fake.word()}.py",
        "old_string": "assert a == 1\nassert b == 2\n",
        "new_string": "assert a == 1\n",
    }

    # Act
    findings = findings_for("Edit", tool_input)

    # Assert
    assert findings == ["assertions drop from 2 to 1"]


def test_multiedit_moving_an_assertion_between_edits_is_allowed() -> None:
    # Arrange
    tool_input = {
        "file_path": f"/repo/tests/test_{fake.word()}.py",
        "edits": [
            {"old_string": "assert a == 1\n", "new_string": "a = 1\n"},
            {"old_string": "b = 2\n", "new_string": "assert a == 1\nb = 2\n"},
        ],
    }

    # Act
    findings = findings_for("MultiEdit", tool_input)

    # Assert
    assert findings == []


def test_write_compares_against_the_file_on_disk(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "tests" / f"test_{fake.word()}.py"
    target.parent.mkdir(parents=True)
    target.write_text("def test_a():\n    assert 1 == 1\n", encoding="utf-8")
    tool_input = {"file_path": str(target), "content": ""}

    # Act
    findings = findings_for("Write", tool_input)

    # Assert
    assert findings == ["assertions drop from 1 to 0", "test cases drop from 1 to 0"]


def test_write_of_a_new_test_file_is_allowed(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "tests" / f"test_{fake.word()}.py"
    tool_input = {"file_path": str(target), "content": "def test_a():\n    assert 1\n"}

    # Act
    findings = findings_for("Write", tool_input)

    # Assert
    assert findings == []


def test_write_over_an_unreadable_file_fails_closed(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "tests"
    target.mkdir()
    tool_input = {"file_path": str(target), "content": ""}

    # Act
    findings = findings_for("Write", tool_input)

    # Assert
    assert findings == [UNREADABLE]


COMMITTED = "def test_a():\n    assert a == 1\n"
ADDED = "\n\ndef test_b():\n    assert b == 2\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _committed_test_file(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", f"{fake.user_name()}@repo.test")
    _git(repo, "config", "user.name", fake.name())
    _git(repo, "config", "commit.gpgsign", "false")
    target = repo / "tests" / "test_x.py"
    target.write_text(COMMITTED, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return target


def test_removing_tests_that_no_commit_holds_is_allowed(tmp_path: Path) -> None:
    # Arrange
    target = _committed_test_file(tmp_path)
    target.write_text(COMMITTED + ADDED, encoding="utf-8")
    tool_input = {"file_path": str(target), "old_string": ADDED, "new_string": ""}

    # Act
    findings = findings_for("Edit", tool_input)

    # Assert
    assert findings == []


def test_removing_a_committed_test_is_still_reported(tmp_path: Path) -> None:
    # Arrange
    target = _committed_test_file(tmp_path)
    tool_input = {"file_path": str(target), "old_string": COMMITTED, "new_string": ""}

    # Act
    findings = findings_for("Edit", tool_input)

    # Assert
    assert findings == ["assertions drop from 1 to 0", "test cases drop from 1 to 0"]


def test_a_multiedit_removing_uncommitted_tests_everywhere_is_allowed(
    tmp_path: Path,
) -> None:
    # Arrange
    target = _committed_test_file(tmp_path)
    target.write_text(COMMITTED + ADDED + ADDED, encoding="utf-8")
    edits = [{"old_string": ADDED, "new_string": "", "replace_all": True}]
    tool_input = {"file_path": str(target), "edits": edits}

    # Act
    findings = findings_for("MultiEdit", tool_input)

    # Assert
    assert findings == []


def test_rewriting_a_file_no_commit_holds_is_allowed(tmp_path: Path) -> None:
    # Arrange
    target = _committed_test_file(tmp_path).parent / "test_new.py"
    target.write_text(COMMITTED, encoding="utf-8")
    tool_input = {"file_path": str(target), "content": ""}

    # Act
    findings = findings_for("Write", tool_input)

    # Assert
    assert findings == []


def test_an_edit_whose_old_text_is_missing_keeps_the_finding(tmp_path: Path) -> None:
    # Arrange
    target = _committed_test_file(tmp_path)
    tool_input = {"file_path": str(target), "old_string": ADDED, "new_string": ""}

    # Act
    findings = findings_for("Edit", tool_input)

    # Assert
    assert findings == ["assertions drop from 1 to 0", "test cases drop from 1 to 0"]


def test_without_git_the_finding_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    target = _committed_test_file(tmp_path)
    target.write_text(COMMITTED + ADDED, encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools"))
    tool_input = {"file_path": str(target), "old_string": ADDED, "new_string": ""}

    # Act
    findings = findings_for("Edit", tool_input)

    # Assert
    assert findings == ["assertions drop from 1 to 0", "test cases drop from 1 to 0"]


def test_a_git_show_that_times_out_keeps_the_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    target = _committed_test_file(tmp_path)
    target.write_text(COMMITTED + ADDED, encoding="utf-8")
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "git"
    stub.write_text(
        "#!/bin/sh\n"
        'case " $* " in\n'
        f'  *" rev-parse "*) echo "{target.parent.parent.resolve()}" ;;\n'
        '  *" show "*) sleep 10 ;;\n'
        f'  *) exec "{shutil.which("git")}" "$@" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(assertion_weakening, "GIT_TIMEOUT_SECONDS", 2)
    tool_input = {"file_path": str(target), "old_string": ADDED, "new_string": ""}

    # Act
    findings = findings_for("Edit", tool_input)

    # Assert
    assert findings == ["assertions drop from 1 to 0", "test cases drop from 1 to 0"]


def test_an_unreadable_target_keeps_the_finding(tmp_path: Path) -> None:
    # Arrange
    target = _committed_test_file(tmp_path).parent / "test_dir.py"
    target.mkdir()
    tool_input = {"file_path": str(target), "old_string": ADDED, "new_string": ""}

    # Act
    findings = findings_for("Edit", tool_input)

    # Assert
    assert findings == ["assertions drop from 1 to 0", "test cases drop from 1 to 0"]


def test_other_tools_report_nothing() -> None:
    # Arrange
    tool_input = {"file_path": f"/repo/tests/test_{fake.word()}.py"}

    # Act
    findings = findings_for("Read", tool_input)

    # Assert
    assert findings == []

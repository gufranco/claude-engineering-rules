from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.guard_runner import (  # noqa: E402
    MAX_FINDINGS_PER_FILE,
    Edit,
    Finding,
    collect_edits,
    has_blocking,
    render_findings,
)


def test_collect_edits_reads_write_content():
    # Arrange
    tool_input = {"file_path": "/repo/a.py", "content": "x = 1\n"}

    # Act
    edits = collect_edits("Write", tool_input)

    # Assert
    assert edits == [Edit(path="/repo/a.py", text="x = 1\n", full_file=True)]


def test_collect_edits_reads_every_multiedit_fragment():
    # Arrange
    tool_input = {
        "file_path": "/repo/a.go",
        "edits": [{"new_string": "a"}, {"new_string": "b"}],
    }

    # Act
    edits = collect_edits("MultiEdit", tool_input)

    # Assert
    assert edits == [
        Edit(path="/repo/a.go", text="a", full_file=False),
        Edit(path="/repo/a.go", text="b", full_file=False),
    ]


def test_collect_edits_ignores_other_tools():
    # Arrange
    tool_input = {"command": "ls"}

    # Act
    edits = collect_edits("Bash", tool_input)

    # Assert
    assert edits == []


def test_render_findings_caps_each_file():
    # Arrange
    findings = tuple(Finding(line=n, message=f"hit {n}") for n in range(1, 20))

    # Act
    rendered = render_findings("Intro:", [("/repo/a.rb", findings)])

    # Assert
    assert rendered.count("  L") == MAX_FINDINGS_PER_FILE


def test_render_findings_labels_advisory_hits():
    # Arrange
    findings = (Finding(line=3, message="dataclass is mutable", blocking=False),)

    # Act
    rendered = render_findings("Intro:", [("/repo/a.py", findings)])

    # Assert
    assert rendered.splitlines() == [
        "Intro:",
        "/repo/a.py:",
        "  L3: dataclass is mutable (advisory)",
    ]


def test_has_blocking_is_false_for_advisory_only():
    # Arrange
    findings = [("/repo/a.py", (Finding(line=1, message="m", blocking=False),))]

    # Act
    blocking = has_blocking(findings)

    # Assert
    assert blocking is False


def test_has_blocking_is_true_when_any_hit_blocks():
    # Arrange
    findings = [
        ("/repo/a.py", (Finding(line=1, message="m", blocking=False),)),
        ("/repo/b.py", (Finding(line=2, message="n"),)),
    ]

    # Act
    blocking = has_blocking(findings)

    # Assert
    assert blocking is True

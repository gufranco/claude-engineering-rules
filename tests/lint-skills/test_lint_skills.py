from __future__ import annotations

import json


from _helpers.lint_skills_support import (
    make_skill,
    run_linter,
)


def test_full_template_passes_in_strict_mode(tmp_path):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Example skill that demonstrates the full template format expected by the linter."\n'
        'argument-hint: "/example <target>"\n'
        'allowed-tools: "Read, Edit"'
    )
    body = (
        "## Overview\nintro\n"
        "## When to Use\ntriggers\n"
        "## Process\nsteps\n"
        "## Common Rationalizations\nfailure modes\n"
        "## Red Flags\nwarnings\n"
        "## Verification\nself-check\n"
    )
    sk = make_skill(tmp_path, "example", fm, body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_accepts_section_aliases(tmp_path):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Skill with alias section names that should map to the canonical six."\n'
        'argument-hint: "/x"\n'
        'allowed-tools: "Read"'
    )
    body = (
        "## Summary\nintro\n"
        "## Triggers\nwhen to use\n"
        "## Steps\nprocess\n"
        "## Anti-patterns\ncommon rationalizations\n"
        "## Smells\nred flags\n"
        "## Self-check\nverification\n"
    )
    sk = make_skill(tmp_path, "example", fm, body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_errors_on_missing_frontmatter(tmp_path):
    # Arrange
    skill_dir = tmp_path / "skills" / "bad"
    skill_dir.mkdir(parents=True)
    sk = skill_dir / "SKILL.md"
    sk.write_text("Just a body with no frontmatter.\n## Section\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "missing-frontmatter" in proc.stdout


def test_errors_on_missing_name(tmp_path):
    # Arrange
    fm = 'description: "A description without a name field, which should fail the linter."'
    sk = make_skill(tmp_path, "x", fm, "## Section\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "missing-name" in proc.stdout


def test_errors_on_name_dir_mismatch(tmp_path):
    # Arrange
    fm = (
        "name: wrong\n"
        'description: "Name field does not match the parent directory name as required."'
    )
    sk = make_skill(tmp_path, "actual", fm, "## Section\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "name-mismatch" in proc.stdout


def test_errors_on_missing_description(tmp_path):
    # Arrange
    fm = "name: example\n"
    sk = make_skill(tmp_path, "example", fm, "## Section\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "missing-description" in proc.stdout


def test_errors_on_no_sections(tmp_path):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Skill with valid frontmatter but no body sections at all."'
    )
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    sk = skill_dir / "SKILL.md"
    sk.write_text(f"---\n{fm}\n---\nJust prose, no headings.\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "no-sections" in proc.stdout


def test_warns_on_short_description(tmp_path):
    # Arrange
    fm = "name: example\ndescription: too short"
    sk = make_skill(tmp_path, "example", fm, "## Overview\nx\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "short-description" in proc.stdout


def test_warns_on_missing_argument_hint(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."\n'
        'allowed-tools: "Read"'
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "missing-argument-hint" in proc.stdout


def test_warns_on_missing_tool_scope(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."\n'
        'argument-hint: "/example"'
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "missing-tool-scope" in proc.stdout


def test_warns_on_missing_sections(tmp_path):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."\n'
        'argument-hint: "/example"\n'
        'allowed-tools: "Read"'
    )
    body = "## Overview\nx\n## When to Use\nx\n"
    sk = make_skill(tmp_path, "example", fm, body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "missing-sections" in proc.stdout


def test_strict_mode_fails_on_warnings(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."\n'
        'allowed-tools: "Read"'
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 1
    assert "[WARN ] missing-argument-hint: no `argument-hint` declared" in proc.stdout
    assert "1 files scanned, 0 errors, 1 warnings" in proc.stdout


def test_discovers_the_skill_file_inside_a_directory_argument(tmp_path):
    # Arrange
    fm = (
        "name: x\n"
        'description: "Adequate description with enough characters to pass the length check."'
    )
    sk = make_skill(
        tmp_path,
        "x",
        fm,
        "## Overview\n## When to Use\n## Process\n## Common Rationalizations\n## Red Flags\n## Verification\n",
    )
    skill_dir = sk.parent

    # Act
    proc = run_linter([str(skill_dir)])

    # Assert
    assert f"\n{sk}\n" in proc.stdout
    assert "1 files scanned, 0 errors, 2 warnings" in proc.stdout


def test_json_output(tmp_path):
    # Arrange
    fm = "description: missing name"
    sk = make_skill(tmp_path, "x", fm, "## Overview\n")

    # Act
    proc = run_linter([str(sk), "--json"])

    # Assert
    assert proc.returncode == 1
    parsed = json.loads(proc.stdout)
    codes = [f["code"] for file in parsed["files"] for f in file["findings"]]
    assert codes == [
        "missing-name",
        "short-description",
        "missing-argument-hint",
        "missing-tool-scope",
        "missing-sections",
    ]


def test_fix_hints_emit_extra_lines(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."'
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--fix-hints"])

    # Assert
    assert proc.returncode == 0
    assert 'Add: argument-hint: "<example invocation>"' in proc.stdout
    assert "1 files scanned, 0 errors, 2 warnings" in proc.stdout


def test_no_files_returns_error(tmp_path):
    # Arrange
    empty = tmp_path / "nothing"
    empty.mkdir()

    # Act
    proc = run_linter([str(empty)])

    # Assert
    assert proc.returncode == 1
    assert "no SKILL.md" in proc.stderr

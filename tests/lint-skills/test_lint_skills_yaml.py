from __future__ import annotations


from _helpers.lint_skills_support import (
    COMPLETE_FIELDS,
    make_skill,
    run_linter,
)


def test_errors_on_unquoted_colon_space_in_description(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: Ship code. Subcommands: commit, pr, release, checks.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "invalid-yaml: line 3" in proc.stdout


def test_errors_on_value_starting_with_reserved_indicator(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: @mention starts this description and breaks strict parsers.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "reserved indicator '@'" in proc.stdout


def test_errors_on_trailing_text_after_quoted_scalar(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "A quoted description" followed by stray trailing text.\n'
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "text after the closing quote" in proc.stdout


def test_errors_on_colon_space_in_plain_continuation_line(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: A long description that wraps onto a second line\n"
        "  where a note: breaks the mapping.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "invalid-yaml: line 4" in proc.stdout


def test_errors_when_hash_after_space_truncates_plain_description(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: Fix a GitHub issue. Use when user says "fix issue #N" or similar.\n'
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "truncated-by-comment: line 3" in proc.stdout


def test_errors_when_hash_after_space_truncates_continuation_line(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: A long description that wraps onto a second line\n"
        "  and then mentions issue #12 in passing.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "truncated-by-comment: line 4" in proc.stdout


def test_accepts_hash_inside_quoted_description(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: 'Fix a GitHub issue. Use when user says \"fix issue #N\" or similar.'\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_accepts_hash_without_preceding_space_in_plain_value(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: Adequate description naming C# and issue-#7 without a comment marker.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_accepts_quoted_description_containing_colon_space(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Ship code. Subcommands: commit, pr, release, and checks."\n'
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_accepts_block_sequence_tool_list(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: Adequate description with enough characters to pass the length check.\n"
        'argument-hint: "/example"\n'
        "allowed-tools:\n"
        "  - Read\n"
        "  - Edit"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout

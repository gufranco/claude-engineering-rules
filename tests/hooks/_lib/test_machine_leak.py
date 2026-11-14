from __future__ import annotations

import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.machine_identity import Identifier, Kind  # noqa: E402
from _lib.machine_leak import Finding, added_lines, scan_lines  # noqa: E402

FAKER_SEED = 20261115


@pytest.fixture
def faker() -> Faker:
    generator = Faker()
    generator.seed_instance(FAKER_SEED)
    return generator


@pytest.fixture
def handle(faker: Faker) -> str:
    return faker.lexify("zq?????")


@pytest.fixture
def full_name(faker: Faker) -> str:
    return f"{faker.lexify('Zq????')} {faker.lexify('Xv????')}"


def _identity(handle: str, full_name: str) -> list[Identifier]:
    return [
        Identifier(Kind.HOME_PATH, f"/Users/{handle}"),
        Identifier(Kind.USERNAME, handle),
        Identifier(Kind.REAL_NAME, full_name),
        Identifier(Kind.WORKSPACE, "@ Qorvath"),
        Identifier(Kind.WINDOW, "Plimbus"),
    ]


def _scan(path: str, text: str, handle: str, full_name: str) -> list[Finding]:
    return scan_lines([(path, 1, text)], _identity(handle, full_name))


def test_a_home_path_is_reported_once_as_a_path(handle, full_name) -> None:
    # Arrange
    text = f'ROOT = "/Users/{handle}/data"'

    # Act
    found = _scan("app.py", text, handle, full_name)

    # Assert
    assert found == [Finding("app.py", 1, Kind.HOME_PATH, f"/Users/{handle}")]


def test_a_folder_name_inside_a_neutral_path_is_reported(handle, full_name) -> None:
    # Arrange
    text = 'cd "/home/u/@ Qorvath/project"'

    # Act
    found = _scan("t.bats", text, handle, full_name)

    # Assert
    assert [f.kind for f in found] == [Kind.WORKSPACE]


def test_a_window_name_is_matched_case_insensitively(handle, full_name) -> None:
    # Arrange
    text = "persist_join window main 2 plimbus 1"

    # Act
    found = _scan("t.bats", text, handle, full_name)

    # Assert
    assert [f.token for f in found] == ["plimbus"]


def test_a_token_inside_a_longer_word_is_not_reported(handle, full_name) -> None:
    # Arrange
    text = "PlimbusExtra and xplimbus"

    # Act
    found = _scan("a.txt", text, handle, full_name)

    # Assert
    assert found == []


@pytest.mark.parametrize(
    "template",
    [
        "https://github.com/{h}/repo",
        "git@github.com:{h}/repo.git",
        "* @{h}",
        "{h}@users.noreply.github.com",
        "brew tap {h}/tap",
        "  owner: {h}",
        "![ci](https://img.shields.io/github/license/{h}/repo)",
        "gh api --method POST repos/{h}/tap/dispatches",
        "the {h}-tap-bot app",
        'assert_equal "built from {h}/#{{name}}"',
        "        <publisher>{h}</publisher>",
    ],
)
def test_the_login_name_is_allowed_as_a_forge_handle(template, handle, full_name):
    # Arrange
    text = template.format(h=handle)

    # Act
    found = _scan("README.md", text, handle, full_name)

    # Assert
    assert found == []


def test_the_login_name_as_a_plain_argument_is_reported(handle, full_name) -> None:
    # Arrange
    text = f'Type "tool keys {handle}"'

    # Act
    found = _scan("demo.tape", text, handle, full_name)

    # Assert
    assert [f.kind for f in found] == [Kind.USERNAME]


@pytest.mark.parametrize(
    ("path", "template"),
    [
        ("src/a.c", "// SPDX-FileCopyrightText: 2026 {n}"),
        ("README.md", "[MIT](LICENSE), copyright {n}."),
        ("package.json", '  "author": "{n}",'),
        ("LICENSE", "Permission granted by {n}"),
        ("docs/CODE_OF_CONDUCT.md", "contact {n}"),
        ("p/0001-fix.patch", "From: {n} <a@users.noreply.github.com>"),
        ("AGENTS.md", "| approved_by | {n}, 2026-10-13 |"),
        ("pyproject.toml", '  {{ name = "{n}" }},'),
    ],
)
def test_the_real_name_is_allowed_in_authorship(path, template, handle, full_name):
    # Arrange
    text = template.format(n=full_name)

    # Act
    found = _scan(path, text, handle, full_name)

    # Assert
    assert found == []


def test_the_real_name_in_a_fixture_is_reported(handle, full_name) -> None:
    # Arrange
    text = f'run tool --preparer "{full_name}"'

    # Act
    found = _scan("test/build.bats", text, handle, full_name)

    # Assert
    assert [f.kind for f in found] == [Kind.REAL_NAME]


def test_a_machine_path_is_reported_even_on_an_authorship_line(handle, full_name):
    # Arrange
    text = f"Copyright {full_name}, built in /Users/{handle}/src"

    # Act
    found = _scan("LICENSE", text, handle, full_name)

    # Assert
    assert [f.kind for f in found] == [Kind.HOME_PATH]


def test_vendored_paths_are_not_scanned(handle, full_name) -> None:
    # Arrange
    text = f"/Users/{handle}"

    # Act
    found = _scan("vendor/lib/a.c", text, handle, full_name)

    # Assert
    assert found == []


def test_no_identifiers_report_nothing() -> None:
    # Arrange
    lines = [("a.txt", 1, "anything at all")]

    # Act
    found = scan_lines(lines, [])

    # Assert
    assert found == []


def test_added_lines_skip_lines_the_file_already_held() -> None:
    # Arrange
    before = "keep\nold\nkeep\n"
    after = "keep\nnew\nkeep\nkeep\n"

    # Act
    result = added_lines("f.txt", before, after)

    # Assert
    assert result == [("f.txt", 2, "new"), ("f.txt", 4, "keep")]


def test_the_login_name_as_a_fixture_expectation_is_reported(handle, full_name):
    # Arrange
    text = f'[[ "${{output}}" == "{handle}" ]]'

    # Act
    found = _scan("test/git.bats", text, handle, full_name)

    # Assert
    assert [f.kind for f in found] == [Kind.USERNAME]


def test_another_account_is_allowed_only_as_a_forge_handle(handle, full_name):
    # Arrange
    other = Identifier(Kind.ACCOUNT, "acme-corp")
    lines = [
        ("a.md", 1, "see https://github.com/acme-corp/app"),
        ("t.bats", 2, 'run accounts "acme-corp=someone"'),
    ]

    # Act
    found = scan_lines(lines, [*_identity(handle, full_name), other])

    # Assert
    assert [(f.line, f.kind) for f in found] == [(2, Kind.ACCOUNT)]

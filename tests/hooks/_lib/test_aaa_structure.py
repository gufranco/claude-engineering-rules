from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.aaa_structure import (  # noqa: E402
    CaseLanguage,
    markers_in,
    Violation,
    case_language,
    find_cases,
    violations,
)

PY_GOOD = (
    "def test_a():\n"
    "    # Arrange\n"
    "    x = 1\n"
    "\n"
    "    # Act\n"
    "    y = x + 1\n"
    "\n"
    "    # Assert\n"
    "    assert y == 2\n"
)
JS_GOOD = (
    "describe('a', () => {\n"
    "  it('adds', async () => {\n"
    "    // Arrange\n"
    "    const x = 1\n"
    "\n"
    "    // Act\n"
    "    const y = x + 1\n"
    "\n"
    "    // Assert\n"
    "    expect(y).toBe(2)\n"
    "  })\n"
    "})\n"
)
GO_GOOD = (
    "package a\n\n"
    "func TestAdd(t *testing.T) {\n"
    "\t// Arrange\n"
    "\tx := 1\n"
    "\n"
    "\t// Act\n"
    "\ty := x + 1\n"
    "\n"
    "\t// Assert\n"
    "\tif y != 2 {\n"
    "\t\tt.Fatal(y)\n"
    "\t}\n"
    "}\n"
)
BATS_GOOD = (
    '@test "adds" {\n'
    "  # Arrange\n"
    "  x=1\n"
    "\n"
    "  # Act\n"
    '  run echo "${x}"\n'
    "\n"
    "  # Assert\n"
    '  [ "$output" = "1" ]\n'
    "}\n"
)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/test_a.py", CaseLanguage.PYTHON),
        ("src/a.test.ts", CaseLanguage.JAVASCRIPT),
        ("src/a.spec.mjs", CaseLanguage.JAVASCRIPT),
        ("pkg/a_test.go", CaseLanguage.GO),
        ("tests/a.bats", CaseLanguage.BATS),
        ("src/a.py", None),
        ("tests/a.rb", None),
        ("pkg/a.go", None),
    ],
)
def test_resolves_the_test_language(path: str, expected: CaseLanguage | None) -> None:
    # Arrange
    candidate = path

    # Act
    language = case_language(candidate)

    # Assert
    assert language == expected


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("tests/test_a.py", PY_GOOD),
        (
            "tests/test_a.py",
            "class TestA:\n    "
            + PY_GOOD.replace("\n", "\n    ").replace("(", "(self", 1),
        ),
        ("src/a.test.ts", JS_GOOD),
        (
            "src/a.test.ts",
            JS_GOOD.replace(
                "it('adds', async () =>", "test.each([[1]])('adds %s', function (n)"
            ),
        ),
        ("pkg/a_test.go", GO_GOOD),
        ("tests/a.bats", BATS_GOOD),
    ],
)
def test_accepts_a_well_formed_test(path: str, text: str) -> None:
    # Arrange
    before = ""

    # Act
    found = violations(path, before, text)

    # Assert
    assert found == []


@pytest.mark.parametrize(
    ("path", "text", "reason"),
    [
        ("tests/test_a.py", PY_GOOD.replace("    # Act\n", ""), "missing Act"),
        ("tests/test_a.py", PY_GOOD.replace("# Assert", "# Act"), "duplicate Act"),
        (
            "tests/test_a.py",
            PY_GOOD.replace("# Act", "# TMP")
            .replace("# Assert", "# Act")
            .replace("# TMP", "# Assert"),
            "out of order",
        ),
        ("tests/test_a.py", PY_GOOD.replace("# Assert", "# Assert: y"), "not bare"),
        (
            "tests/test_a.py",
            PY_GOOD.replace("    x = 1\n\n", "    x = 1\n"),
            "one blank line must precede the Act",
        ),
        (
            "tests/test_a.py",
            PY_GOOD.replace("    x = 1\n\n", "    x = 1\n\n\n"),
            "one blank line must precede the Act",
        ),
        (
            "tests/test_a.py",
            PY_GOOD.replace("    # Arrange\n", "    z = 0\n    # Arrange\n"),
            "open with the Arrange",
        ),
        (
            "tests/test_a.py",
            PY_GOOD.replace("    y = x + 1\n", ""),
            "Act block is empty",
        ),
        (
            "tests/test_a.py",
            "def test_a(): assert True\n",
            "missing Arrange, Act, Assert",
        ),
        ("src/a.test.ts", JS_GOOD.replace("    // Arrange\n", ""), "missing Arrange"),
        (
            "src/a.test.ts",
            "it('x', () => expect(1).toBe(1))\n",
            "missing Arrange, Act, Assert",
        ),
        ("pkg/a_test.go", GO_GOOD.replace("\t// Assert\n", ""), "missing Assert"),
        ("tests/a.bats", BATS_GOOD.replace("  # Act\n", "  # Act now\n"), "not bare"),
    ],
)
def test_reports_a_malformed_test(path: str, text: str, reason: str) -> None:
    # Arrange
    before = ""

    # Act
    found = violations(path, before, text)

    # Assert
    assert len(found) == 1
    assert reason in found[0].reason


def test_ignores_an_untouched_legacy_test() -> None:
    # Arrange
    legacy = "def test_old():\n    assert True\n\n\n"

    # Act
    found = violations("tests/test_a.py", legacy, legacy + PY_GOOD)

    # Assert
    assert found == []


def test_reports_a_legacy_test_once_it_changes() -> None:
    # Arrange
    legacy = "def test_old():\n    assert True\n"

    # Act
    found = violations("tests/test_a.py", legacy, legacy.replace("True", "1"))

    # Assert
    assert found == [Violation("test_old", 1, "missing Arrange, Act, Assert")]


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("tests/test_a.py", "def test_a(:\n"),
        ("tests/test_a.py", "def helper():\n    pass\n"),
        ("src/a.test.ts", "const it = 1\nfor (const test of tests) {}\nre.test(s)\n"),
        ("src/a.test.ts", "it.todo('later')\ntest(helper)\n"),
        ("src/a.test.ts", "it\n"),
        ("pkg/a_test.go", "func TestMain(m *testing.M) {}\nfunc helper() {}\n"),
    ],
)
def test_finds_no_case_in_non_test_code(path: str, text: str) -> None:
    # Arrange
    language = case_language(path)

    # Act
    cases = find_cases(text, language)

    # Assert
    assert language is not None
    assert cases == []


def test_names_a_case_after_its_title() -> None:
    # Arrange
    text = "it.each`\n  a | b\n`('sums $a', ({ a }) => {\n})\n"

    # Act
    cases = find_cases(text, CaseLanguage.JAVASCRIPT)

    # Assert
    assert [case.name for case in cases] == ["sums $a"]


def test_skips_an_options_object_before_the_callback() -> None:
    # Arrange
    text = "it('x', { timeout: 5 }, () => {\n  // Arrange\n  a()\n})\n"

    # Act
    cases = find_cases(text, CaseLanguage.JAVASCRIPT)

    # Assert
    assert [(case.first_line, case.last_line) for case in cases] == [(1, 2)]


def test_reports_nothing_for_an_unsupported_path() -> None:
    # Arrange
    text = "it 'x' do\nend\n"

    # Act
    found = violations("spec/a_spec.rb", "", text)

    # Assert
    assert found == []


def test_finds_no_markers_in_python_that_does_not_tokenize() -> None:
    # Arrange
    text = "def test_a(:\n    # Arrange\n"

    # Act
    markers = markers_in(text, CaseLanguage.PYTHON)

    # Assert
    assert markers == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("it('x', () => {\n  // Arrange\n", ["x"]),
        ("it.a.b.c.d.e.f.g.h.i('x', () => {\n})\n", []),
    ],
)
def test_tolerates_an_unclosed_or_overlong_call(text: str, expected: list[str]) -> None:
    # Arrange
    language = CaseLanguage.JAVASCRIPT

    # Act
    cases = find_cases(text, language)

    # Assert
    assert [case.name for case in cases] == expected


def test_reports_only_the_malformed_one_of_two_changed_tests() -> None:
    # Arrange
    text = PY_GOOD + "\n\n" + "def test_b():\n    assert True\n"

    # Act
    found = violations("tests/test_a.py", "", text)

    # Assert
    assert [violation.name for violation in found] == ["test_b"]

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.analyzer_parsers import (  # noqa: E402
    RawFinding,
    parse_checkstyle,
    parse_clang_tidy,
    parse_dart,
    parse_golangci,
    parse_luacheck,
    parse_pmd,
    parse_pyright,
    parse_rubocop,
    parse_ruff,
    parse_swiftlint,
)


def test_parse_clang_tidy_reads_check_names():
    # Arrange
    output = (
        "/r/a.c:1:10: error: 'nds.h' file not found [clang-diagnostic-error]\n"
        "/r/a.c:7:14: warning: pointer parameter 'values' can be pointer to const "
        "[readability-non-const-parameter,-warnings-as-errors]\n"
        "6 warnings generated.\n"
    )

    # Act
    findings = parse_clang_tidy(output)

    # Assert
    assert findings == (
        RawFinding("/r/a.c", 1, "clang-diagnostic-error", "'nds.h' file not found"),
        RawFinding(
            "/r/a.c",
            7,
            "readability-non-const-parameter",
            "pointer parameter 'values' can be pointer to const",
        ),
    )


def test_parse_golangci_reads_the_json_line():
    # Arrange
    output = (
        json.dumps(
            {
                "Issues": [
                    {
                        "FromLinter": "reassign",
                        "Text": "reassigning variable",
                        "Pos": {"Filename": "a.go", "Line": 16},
                    }
                ]
            }
        )
        + "\n0 issues.\n"
    )

    # Act
    findings = parse_golangci(output)

    # Assert
    assert findings == (RawFinding("a.go", 16, "reassign", "reassigning variable"),)


def test_parse_ruff_reads_codes():
    # Arrange
    output = json.dumps(
        [
            {
                "code": "B006",
                "filename": "/r/a.py",
                "location": {"row": 12},
                "message": "Do not use mutable",
            }
        ]
    )

    # Act
    findings = parse_ruff(output)

    # Assert
    assert findings == (RawFinding("/r/a.py", 12, "B006", "Do not use mutable"),)


def test_parse_pyright_converts_zero_based_lines():
    # Arrange
    output = json.dumps(
        {
            "generalDiagnostics": [
                {
                    "file": "/r/a.py",
                    "rule": "reportConstantRedefinition",
                    "range": {"start": {"line": 9}},
                    "message": "constant",
                },
                {
                    "file": "/r/a.py",
                    "range": {"start": {"line": 0}},
                    "message": "import unresolved",
                },
            ]
        }
    )

    # Act
    findings = parse_pyright(output)

    # Assert
    assert findings == (
        RawFinding("/r/a.py", 10, "reportConstantRedefinition", "constant"),
        RawFinding("/r/a.py", 1, "pyright", "import unresolved"),
    )


def test_parse_rubocop_reads_offenses():
    # Arrange
    output = json.dumps(
        {
            "files": [
                {
                    "path": "a.rb",
                    "offenses": [
                        {
                            "cop_name": "Style/MutableConstant",
                            "location": {"line": 1},
                            "message": "Freeze",
                        }
                    ],
                }
            ]
        }
    )

    # Act
    findings = parse_rubocop(output)

    # Assert
    assert findings == (RawFinding("a.rb", 1, "Style/MutableConstant", "Freeze"),)


def test_parse_luacheck_reads_codes():
    # Arrange
    output = "a.lua:3:3: (W111) setting non-standard global variable 'total'\n\nTotal: 1 warning\n"

    # Act
    findings = parse_luacheck(output)

    # Assert
    assert findings == (
        RawFinding("a.lua", 3, "W111", "setting non-standard global variable 'total'"),
    )


def test_parse_checkstyle_reads_detekt_xml():
    # Arrange
    output = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<checkstyle version="4.3">\n'
        '<file name="/r/A.kt">\n'
        '\t<error line="1" column="33" severity="warning" message="name is var" source="detekt.DataClassShouldBeImmutable" />\n'
        "</file>\n</checkstyle>\n"
    )

    # Act
    findings = parse_checkstyle(output)

    # Assert
    assert findings == (
        RawFinding("/r/A.kt", 1, "DataClassShouldBeImmutable", "name is var"),
    )


def test_parse_pmd_reads_violations():
    # Arrange
    output = json.dumps(
        {
            "files": [
                {
                    "filename": "A.java",
                    "violations": [
                        {
                            "rule": "ImmutableField",
                            "beginline": 4,
                            "description": "may be final",
                        }
                    ],
                }
            ]
        }
    )

    # Act
    findings = parse_pmd(output)

    # Assert
    assert findings == (RawFinding("A.java", 4, "ImmutableField", "may be final"),)


def test_parse_swiftlint_reads_rule_ids():
    # Arrange
    output = json.dumps(
        [
            {
                "file": "/r/a.swift",
                "line": 3,
                "rule_id": "shared_static_var",
                "reason": "static var",
            }
        ]
    )

    # Act
    findings = parse_swiftlint(output)

    # Assert
    assert findings == (RawFinding("/r/a.swift", 3, "shared_static_var", "static var"),)


def test_parse_dart_reads_machine_format():
    # Arrange
    output = "ERROR|LINT|PREFER_FINAL_LOCALS|/t/lib/a.dart|10|5|3|Local variables should be final.\nnoise line\n"

    # Act
    findings = parse_dart(output)

    # Assert
    assert findings == (
        RawFinding(
            "/t/lib/a.dart",
            10,
            "PREFER_FINAL_LOCALS",
            "Local variables should be final.",
        ),
    )


def test_parsers_reject_unparsable_json():
    # Arrange
    output = "not json"

    # Act
    findings = parse_ruff(output)

    # Assert
    assert findings is None


def test_parse_checkstyle_rejects_broken_xml():
    # Arrange
    output = "<checkstyle><file"

    # Act
    findings = parse_checkstyle(output)

    # Assert
    assert findings is None

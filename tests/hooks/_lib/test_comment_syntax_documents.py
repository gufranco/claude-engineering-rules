from __future__ import annotations

import json

import pytest

from _helpers.comment_syntax_support import (
    comment_lines,
    document_view,
    family_for,
    notebook_code,
    reported_numbers,
    resolve_family,
)


def notebook(cells: list[tuple[str, str]], language: str = "python") -> str:
    return json.dumps(
        {
            "metadata": {"language_info": {"name": language}},
            "cells": [
                {"cell_type": kind, "source": source.splitlines(keepends=True)}
                for kind, source in cells
            ],
        }
    )


@pytest.mark.parametrize(
    ("path", "text", "name"),
    [
        ("mat/a.m", "x = 1;\n", "matlab"),
        ("objc/a.m", "@interface A\n@end\n", "c"),
        ("asm/a.inc", "LED = 1\n", "assembly"),
        ("c/a.inc", "static int a;\n", "c"),
        ("m68k/a.s", "    move.w d0,d1\n", "assembly_68k"),
        ("snes/a.asm", "    cmp.w #$0001\n    sta.l $7E0000\n", "assembly"),
        ("z80/a.asm", "    add hl,sp\n    ld a,d\n", "assembly"),
        (".git-hooks/pre-commit", "#!/bin/sh\nexit 0\n", "shell"),
        ("bin/tool", "#!/usr/bin/env python3\n", "python"),
        ("bin/tool", "#!/usr/bin/env -S node --harmony\n", "javascript"),
        ("bin/tool", "#!/usr/bin/osascript\n", "applescript"),
        ("bin/tool", "#!/usr/bin/env ruby\n", "ruby"),
        ("bin/tool", "#!/usr/bin/env\n", None),
        ("bin/tool", "#!/usr/bin/env unknown-interpreter\n", None),
        ("nb/a.ipynb", notebook([("code", "x = 1\n")]), "python"),
        ("nb/a.ipynb", notebook([("code", "x <- 1\n")], "R"), "r"),
        ("nb/a.ipynb", '{"metadata": {"kernelspec": {"language": "julia"}}}', "julia"),
        ("nb/a.ipynb", '{"metadata": []}', "python"),
        ("nb/a.ipynb", '{"metadata": {"kernelspec": {}}}', "python"),
        ("nb/a.ipynb", "not json", "python"),
        ("nb/a.ipynb", "[1]", "python"),
    ],
)
def test_resolves_a_family_from_the_content(
    path: str, text: str, name: str | None
) -> None:
    # Arrange
    candidate = (path, text)

    # Act
    family = resolve_family(*candidate)

    # Assert
    assert getattr(family, "name", None) == name


@pytest.mark.parametrize(
    "path", [".env.example", "config/.env.local.example", ".env.example.local"]
)
def test_exempts_documented_env_examples(path: str) -> None:
    # Arrange
    candidate = path

    # Act
    family = resolve_family(candidate, "# The port the API listens on\nPORT=3000\n")

    # Assert
    assert family is None


def test_scans_only_code_cells_of_a_notebook() -> None:
    # Arrange
    text = notebook(
        [
            ("markdown", "# Title\n"),
            ("code", "x = 1  # note\n"),
            ("code", "y = '# s'\n"),
        ]
    )

    # Act
    view = document_view("nb/a.ipynb", text)

    # Assert
    assert view is not None
    assert comment_lines(view.text, view.family) == [(0, "x = 1  # note")]


def test_builds_no_code_from_a_notebook_without_cells() -> None:
    # Arrange
    text = '{"cells": {}}'

    # Act
    code = notebook_code(text)

    # Assert
    assert code == ""


def test_builds_code_from_a_cell_whose_source_is_a_string() -> None:
    # Arrange
    text = json.dumps({"cells": [{"cell_type": "code", "source": "x = 1"}, "junk"]})

    # Act
    code = notebook_code(text)

    # Assert
    assert code == "x = 1"


def test_returns_no_view_for_an_out_of_scope_path() -> None:
    # Arrange
    path = "README.md"

    # Act
    view = document_view(path, "# Title\n")

    # Assert
    assert view is None


def test_returns_the_text_unchanged_for_a_source_file() -> None:
    # Arrange
    text = "x = 1\n"

    # Act
    view = document_view("src/a.py", text)

    # Assert
    assert view is not None
    assert view.text == text


def test_parses_python_with_an_invalid_escape_without_warning() -> None:
    # Arrange
    family = family_for("src/app.py")

    # Act
    pairs = comment_lines('import re\nPATTERN = "\\d"\n', family)

    # Assert
    assert pairs == []


def test_reports_a_comment_after_a_deeply_nested_interpolation() -> None:
    # Arrange
    family = family_for("scripts/a.sh")
    nested = '$(echo "' * 12 + '")' * 12

    # Act
    pairs = comment_lines(f'echo "{nested}"\n# note\n', family)

    # Assert
    assert reported_numbers(pairs) == (2,)


YAML_SHELL_FLAGGED: list[tuple[str, str, tuple[int, ...]]] = [
    (
        ".github/workflows/ci.yml",
        "jobs:\n  a:\n    steps:\n      - run: |\n          # explain\n          echo hi\n",
        (5,),
    ),
    (
        ".github/workflows/ci.yml",
        "steps:\n  - run: >-\n      echo hi # explain\n",
        (3,),
    ),
    (".github/workflows/ci.yml", "steps:\n  - run: 'echo hi # explain'\n", (2,)),
    (".gitlab-ci.yml", 'job:\n  script:\n    - "echo a # explain"\n', (3,)),
    (
        ".gitlab-ci.yml",
        "job:\n  before_script:\n    - |\n      # explain\n      echo a\n",
        (4,),
    ),
    (".gitlab-ci.yml", "job:\n  after_script: 'echo a # explain'\n", (2,)),
    ("compose.yaml", 'services:\n  a:\n    command: "sh -c run # explain"\n', (3,)),
    (
        "compose.yaml",
        "services:\n  a:\n    entrypoint: |+\n      # explain\n      run\n",
        (4,),
    ),
    ("Taskfile.yml", 'tasks:\n  b:\n    cmds:\n      - "go build # explain"\n', (4,)),
    ("Taskfile.yml", "tasks:\n  b:\n    cmds:\n      - cmd: 'echo # explain'\n", (4,)),
    (
        ".pre-commit-config.yaml",
        "hooks:\n  - id: a\n    entry: 'bash -c x # explain'\n",
        (3,),
    ),
]

YAML_SHELL_CLEAN: list[tuple[str, str]] = [
    (".github/workflows/ci.yml", 'steps:\n  - run: |\n      echo "a # b"\n'),
    (".github/workflows/ci.yml", "description: |\n  # Heading\n  text\n"),
    ("compose.yaml", 'services:\n  a:\n    command: ["sh", "-c", "a # b"]\n'),
    (".gitlab-ci.yml", 'job:\n  script:\n    - echo "#"\n'),
    ("Taskfile.yml", "tasks:\n  b:\n    cmds:\n      - task: other\n"),
]


@pytest.mark.parametrize(("path", "content", "expected"), YAML_SHELL_FLAGGED)
def test_reports_a_shell_comment_inside_a_yaml_shell_key(
    path: str, content: str, expected: tuple[int, ...]
) -> None:
    # Arrange
    family = family_for(path)

    # Act
    pairs = comment_lines(content, family)

    # Assert
    assert reported_numbers(pairs) == expected


@pytest.mark.parametrize(("path", "content"), YAML_SHELL_CLEAN)
def test_ignores_a_hash_that_is_not_a_shell_comment_in_yaml(
    path: str, content: str
) -> None:
    # Arrange
    family = family_for(path)

    # Act
    pairs = comment_lines(content, family)

    # Assert
    assert pairs == []

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.guard_runner import Edit  # noqa: E402
from _lib.polyglot_mutation_scripting import find_lua, find_ruby  # noqa: E402

FROZEN = "# frozen_string_literal: true\n\n"


def _edit(path: str, text: str, *, full_file: bool = True) -> Edit:
    return Edit(path=f"/repo/{path}", text=text, full_file=full_file)


def test_ruby_new_file_without_frozen_string_literal_blocks():
    # Arrange
    edit = _edit("lib/a.rb", "class A\nend\n")

    # Act
    hits = find_ruby(edit)

    # Assert
    assert [(hit.line, hit.blocking) for hit in hits] == [(1, True)]


def test_ruby_fragment_is_not_checked_for_the_magic_comment():
    # Arrange
    edit = _edit("lib/a.rb", "def a\n  1\nend\n", full_file=False)

    # Act
    hits = find_ruby(edit)

    # Assert
    assert hits == ()


def test_ruby_mutable_constant_blocks():
    # Arrange
    edit = _edit("lib/a.rb", FROZEN + "ROLES = [:admin, :user]\nLIMITS = { a: 1 }\n")

    # Act
    hits = find_ruby(edit)

    # Assert
    assert [hit.line for hit in hits] == [3, 4]


def test_ruby_frozen_constant_spanning_lines_passes():
    # Arrange
    edit = _edit("lib/a.rb", FROZEN + "ROLES = [\n  :admin,\n].freeze\nNAME = 'x'\n")

    # Act
    hits = find_ruby(edit)

    # Assert
    assert hits == ()


def test_ruby_schema_file_is_skipped():
    # Arrange
    edit = _edit("db/schema.rb", "ActiveRecord::Schema.define do\nend\n")

    # Act
    hits = find_ruby(edit)

    # Assert
    assert hits == ()


def test_ruby_homebrew_formula_is_skipped():
    # Arrange
    edit = _edit("Formula/tool.rb", "class Tool < Formula\nend\n")

    # Act
    hits = find_ruby(edit)

    # Assert
    assert hits == ()


def test_lua_implicit_global_is_advisory():
    # Arrange
    edit = _edit(
        "a.lua", "local count = 0\nfunction bump(step)\n  total = count + step\nend\n"
    )

    # Act
    hits = find_lua(edit)

    # Assert
    assert [
        (hit.line, hit.blocking, "`total`" in hit.message or "`bump`" in hit.message)
        for hit in hits
    ] == [
        (2, False, True),
        (3, False, True),
    ]


def test_lua_locals_params_and_fields_pass():
    # Arrange
    edit = _edit(
        "a.lua",
        "local M = {}\nlocal function helper(x)\n  x = x + 1\n  return x\nend\nfunction M.run(y)\n  M.last = y\n  for i = 1, 3 do i = i end\nend\nreturn M\n",
    )

    # Act
    hits = find_lua(edit)

    # Assert
    assert hits == ()


def test_ruby_constant_in_an_unclosed_fragment_is_flagged():
    # Arrange
    edit = _edit("lib/a.rb", "ROLES = [\n  :admin,\n", full_file=False)

    # Act
    hits = find_ruby(edit)

    # Assert
    assert [hit.line for hit in hits] == [1]


def test_lua_fragment_is_not_checked():
    # Arrange
    edit = _edit("a.lua", "total = 1\n", full_file=False)

    # Act
    hits = find_lua(edit)

    # Assert
    assert hits == ()

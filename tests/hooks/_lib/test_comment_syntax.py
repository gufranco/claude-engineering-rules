from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.comment_syntax import (  # noqa: E402
    CommentFamily,
    added_comment_lines,
    comment_lines,
    document_view,
    is_test_path,
    mask_code,
    notebook_code,
    resolve_family,
    scan_hits,
)

FLAGGED: list[tuple[str, str, tuple[int, ...]]] = [
    ("src/a.js", 's.replace(/\\s+/g, "_") // explain\n', (1,)),
    ("src/a.tsx", "const a = <b>x</b> // explain\n", (1,)),
    ("src/a.mts", "// note\nconst x = 1\n", (1,)),
    ("src/a.cts", "/* note */\nconst x = 1\n", (1,)),
    ("src/a.ts", "/** doc */\nexport const x = 1\n", (1,)),
    ("src/a.ts", "const x = 1 /* trailing */\n", (1,)),
    ("src/a.java", 'String s = """\n// inside\n""";\n// note\n', (4,)),
    ("src/lib.rs", "/// doc\nfn f() {}\n", (1,)),
    ("src/lib.rs", "//! crate doc\n", (1,)),
    ("src/lib.rs", "fn f(x: &'static str) {}\n// note\n", (2,)),
    ("src/a.cpp", "int n = 1'000;\n// note\n", (2,)),
    ("web/x.php", "# note\n$x = 1;\n", (1,)),
    ("src/a.zig", "// note\nconst x = 1;\n", (1,)),
    ("src/a.sol", "/// @notice doc\ncontract A {}\n", (1,)),
    ("api/a.proto", "// note\nmessage A {}\n", (1,)),
    ("db/schema.prisma", "/// doc\nmodel A {\n  id Int @id\n}\n", (1,)),
    ("app/build.gradle", "// note\napply plugin: 'java'\n", (1,)),
    ("src/a.groovy", "/* note */\ndef x = 1\n", (1,)),
    ("src/app.py", '"""Doc."""\nx = 1\n', (1,)),
    ("src/app.py", 'class A:\n    """Doc."""\n', (2,)),
    ("src/app.py", 'async def f():\n    """Doc."""\n', (2,)),
    ("scripts/a.bash", "#!/usr/bin/env bash\n# note\necho hi\n", (2,)),
    ("scripts/a.zsh", "x=1 # note\n", (1,)),
    ("scripts/a.ksh", "x=1;# note\n", (1,)),
    ("conf/config.fish", "# note\nset x 1\n", (1,)),
    ("tests/run.bats", '# note\n@test "a" {\n  true\n}\n', (1,)),
    ("home/.zshrc", "# note\nexport A=1\n", (1,)),
    ("Dockerfile", "# note\nFROM alpine\n", (1,)),
    ("docker/Dockerfile.prod", "FROM alpine\nRUN echo hi # note\n", (2,)),
    ("docker/app.dockerfile", "# note\nFROM alpine\n", (1,)),
    ("Containerfile", "# note\nFROM alpine\n", (1,)),
    ("lib/a.rb", "=begin\nnote\n=end\nx = 1\n", (1, 2, 3)),
    ("lib/a.rb", "x = 1 # note\n", (1,)),
    ("Gemfile", "# note\ngem 'x'\n", (1,)),
    ("Rakefile", "# note\ntask :a\n", (1,)),
    ("lib/a.pl", "=pod\nnote\n=cut\nmy $x = 1;\n", (1, 2, 3)),
    ("lib/A.pm", "my $x = 1; # note\n", (1,)),
    ("ps/a.ps1", "<# note #>\n$x = 1\n", (1,)),
    ("ps/a.psm1", "# note\n$x = 1\n", (1,)),
    (".github/ci.yml", "# note\nkey: value\n", (1,)),
    ("conf/a.yaml", "key: value # note\n", (1,)),
    ("conf/a.yaml", "title: don't # stop\n", (1,)),
    ("pyproject.toml", "# note\n[tool]\n", (1,)),
    ("Makefile", "# note\nall:\n\techo hi\n", (1,)),
    ("Makefile", "all:\n\techo hi # note\n", (2,)),
    ("mk/rules.mk", "X = 1 # note\n", (1,)),
    ("GNUmakefile", "X = don't # note\n", (1,)),
    ("Justfile", "# note\nbuild:\n    echo hi\n", (1,)),
    (".justfile", "build:\n    echo hi # note\n", (2,)),
    ("infra/main.tf", '# note\nresource "a" "b" {}\n', (1,)),
    ("infra/main.tf", "// note\n", (1,)),
    ("infra/vars.tfvars", "/* note */\nx = 1\n", (1,)),
    ("infra/a.hcl", "x = 1 # note\n", (1,)),
    ("db/q.sql", "-- note\nSELECT 1;\n", (1,)),
    ("db/q.sql", "/* note */\nSELECT 1;\n", (1,)),
    ("db/q.pgsql", "SELECT 1; -- note\n", (1,)),
    ("lua/a.lua", "-- note\nlocal x = 1\n", (1,)),
    ("lua/a.lua", "--[[ note\nmore ]]\nlocal x = 1\n", (1, 2)),
    ("lua/a.lua", "--[==[ note ]==]\nlocal x = 1\n", (1,)),
    ("lua/a.lua", "---@type number\nlocal x = 1\n", (1,)),
    ("src/A.hs", "-- note\nx = 1\n", (1,)),
    ("src/A.hs", "{- outer {- inner -} still -}\nx = 1\n", (1,)),
    ("src/A.elm", "{-| doc -}\nx = 1\n", (1,)),
    ("src/A.purs", "x = 1 -- note\n", (1,)),
    ("web/a.css", "/* note */\na { color: red; }\n", (1,)),
    ("web/a.scss", "// note\na { color: red; }\n", (1,)),
    ("web/a.less", "/* note */\n@x: 1;\n", (1,)),
    ("web/a.sass", "// note\na\n  color: red\n", (1,)),
    ("web/a.html", "<!-- note -->\n<p>x</p>\n", (1,)),
    ("web/a.html", "<script>\n// note\nlet x = 1\n</script>\n", (2,)),
    ("web/a.html", "<style>\n/* note */\n</style>\n", (2,)),
    (
        "web/a.vue",
        "<template><p/></template>\n<script setup>\n/* note */\n</script>\n",
        (3,),
    ),
    ("web/a.svelte", "<!-- note -->\n<p/>\n", (1,)),
    ("web/a.astro", "---\n// note\nconst x = 1\n---\n<p/>\n", (2,)),
    ("data/a.xml", "<!-- note -->\n<a/>\n", (1,)),
    ("img/a.svg", "<svg><!-- note --></svg>\n", (1,)),
    ("r/a.r", "# note\nx <- 1\n", (1,)),
    ("jl/a.jl", "#= note =#\nx = 1\n", (1,)),
    ("jl/a.jl", "x = 1 # note\n", (1,)),
    ("lib/a.ex", "# note\nx = 1\n", (1,)),
    ("lib/a.ex", '@doc """\nDoc.\n"""\ndef f, do: 1\n', (1,)),
    ("lib/a.exs", '@moduledoc "Doc."\n', (1,)),
    ("src/a.erl", "% note\n-module(a).\n", (1,)),
    ("src/a.erl", '-doc("Doc.").\nf() -> 1.\n', (1,)),
    ("src/a.clj", "; note\n(def x 1)\n", (1,)),
    ("src/a.scm", "#| note |#\n(define x 1)\n", (1,)),
    ("src/a.el", ";; note\n(setq x 1)\n", (1,)),
    ("src/a.nim", "#[ note ]#\nlet x = 1\n", (1,)),
    ("src/a.nim", "## doc\nlet x = 1\n", (1,)),
    ("src/a.cr", "# note\nx = 1\n", (1,)),
    ("api/a.graphql", "# note\ntype A {\n  id: ID\n}\n", (1,)),
    ("api/a.gql", "type A {\n  id: ID # note\n}\n", (2,)),
    ("CMakeLists.txt", "# note\nproject(a)\n", (1,)),
    ("cmake/a.cmake", "#[[ note ]]\nset(x 1)\n", (1,)),
    ("setup.cfg", "; note\n[a]\n", (1,)),
    ("conf/a.ini", "# note\n[a]\n", (1,)),
    ("conf/a.properties", "! note\na=1\n", (1,)),
    (".editorconfig", "# note\nroot = true\n", (1,)),
    ("src/a.ml", "(* note *)\nlet x = 1\n", (1,)),
    ("nix/a.nix", "# note\n{ }\n", (1,)),
]

STRINGS_HOLDING_A_TOKEN: list[tuple[str, str]] = [
    ("src/a.js", "/x\\/\\//.test(s)\n"),
    ("scripts/a.sh", 'echo "$(unterminated # x\n'),
    ("src/a.js", "const s = `unterminated // x\n"),
    ("pkg/a.go", "var t = `${ // not a comment`\nvar u = 1\n"),
    ("src/cursor.ts", 'return btoa(v).replace(/\\//g, "_").replace(/=+$/, "")\n'),
    ("src/a.js", "const r = /[/*]'/g\nconst s = typeof /x/\n"),
    ("src/a.tsx", "const a = <b>x</b>\nconst c = n / 2 / 3\n"),
    ("scripts/a.sh", '[[ "$(f color "c #abc")" == "#abc" ]]\n'),
    ("scripts/a.sh", 'echo "${A:-"# d"}"\n'),
    ("infra/locals.tf", 'x = "${join(",", [for n in v : "a/${n}/*"])}"\ny = 1\n'),
    ("src/a.ts", "const t = `a ${f(`#{x}` + '//')} b`\n"),
    ("lib/a.rb", 'x = "#{h["k"]} # z"\n'),
    ("doc/a.tex", "\\setmainfont{Inter}%\n%\n"),
    ("doc/a.tex", "\\begin{lstlisting}\nx = a % 2;\n\\end{lstlisting}\n"),
    ("src/a.mts", 'const u = "http://x"\n'),
    ("src/a.ts", "const t = `a // b ${c} /* d */`\n"),
    ("web/x.php", "#[Attr]\nfunction f() {}\n"),
    ("src/a.zig", 'const s = "a // b";\n'),
    ("src/a.zig", "const s =\n    \\\\ a // b\n;\n"),
    ("scripts/a.sh", "n=${#arr[@]}; echo $# a#b\n"),
    ("scripts/a.sh", "cat <<'EOF'\n# not a comment\nEOF\n"),
    ("scripts/a.sh", "cat <<-EOF\n\t# not a comment\n\tEOF\n"),
    ("scripts/a.sh", "echo $((1 << SHIFT)) '# x'\n"),
    ("scripts/a.sh", "echo 'a\\' \"# b\"\n"),
    ("lib/a.rb", 'x = "#{y} # z"\n'),
    ("lib/a.rb", "x = <<~SQL\n  # inside\nSQL\n"),
    ("lib/a.pl", "my $n = $#arr;\n"),
    ("ps/a.ps1", '$s = "a `" # b"\n'),
    ("ps/a.ps1", '$h = @"\n# inside\n"@\n'),
    ("conf/a.yml", "url: http://x#frag\nmsg: \"a # b\"\nq: 'it''s # x'\n"),
    (
        "conf/a.yml",
        "description: |\n  # prose inside a block scalar\n  text\nnext: 1\n",
    ),
    ("conf/a.yml", "items:\n  - >-\n    # folded text\n"),
    ("pyproject.toml", 'a = "# x"\nb = \'# y\'\nc = """\n# z\n"""\n'),
    ("Makefile", 'all:\n\techo "# x"\n'),
    ("Makefile", "X = a\\#b\n"),
    ("Justfile", "build:\n    #!/usr/bin/env bash\n    echo hi\n"),
    ("infra/main.tf", 'x = "a # b // c /* d */"\ny = <<EOF\n# inside\nEOF\n'),
    ("db/q.sql", "SELECT '-- not', 'it''s /* x */', $$ -- body $$;\n"),
    ("lua/a.lua", 'local s = "-- x"\nlocal t = [[\n-- y\n]]\n'),
    ("src/A.hs", 'x = a --> b\ns = "-- c"\n'),
    ("web/a.css", 'a { background: url("//x/y.png"); }\n'),
    ("web/a.scss", "a { background: url(http://x/y.png); }\n"),
    ("web/a.html", "<p>http://x // y /* z */</p>\n"),
    (
        "web/a.vue",
        "<template><a href=\"#\">x</a></template>\n<script>\nconst u = 'http://x'\n</script>\n",
    ),
    ("r/a.r", 'x <- "# y"\n'),
    ("jl/a.jl", 'x = "# y"\ny = A\'\n'),
    ("lib/a.ex", 'x = "# y"\nc = ?#\n'),
    ("src/a.erl", 'X = "% y", C = $%.\n'),
    ("src/a.clj", '(def x "; y")\n(def c \\;)\n'),
    ("src/a.el", "(setq c ?\\;)\n"),
    ("src/a.nim", 'let x = "# y"\n'),
    ("src/a.cr", 'x = "# y"\n'),
    ("api/a.graphql", 'type A @d(x: "# y") {\n  id: ID\n}\n'),
    ("CMakeLists.txt", 'set(x "# y")\n'),
    ("conf/a.ini", "url = http://x;y#z\n"),
    ("src/a.ml", 'let s = "(* x *)"\n'),
    ("nix/a.nix", '{ s = "# x"; }\n'),
    ("src/app.py", 'x = "# y"\n'),
]

DIRECTIVES: list[tuple[str, str]] = [
    ("conf/a.yml", "# yaml-language-server: $schema=x.json\na: 1\n"),
    ("conf/a.yml", "a: 1 # zizmor: ignore[template-injection]\n"),
    ("conf/a.yml", "# yamllint disable-line rule:line-length\na: 1\n"),
    ("Dockerfile", "# syntax=docker/dockerfile:1\nFROM alpine\n"),
    ("Dockerfile", "# hadolint ignore=DL3008\nRUN x\n"),
    (
        "infra/main.tf",
        '# tflint-ignore: terraform_unused_declarations\nvariable "x" {}\n',
    ),
    ("infra/main.tf", "#tfsec:ignore:aws-s3-enable-bucket-logging\n"),
    ("infra/main.tf", "# checkov:skip=CKV_AWS_18: reason\n"),
    ("db/q.sql", "-- name: GetUser :one\nSELECT 1;\n"),
    ("db/q.sql", "-- +goose Up\nCREATE TABLE a (id int);\n"),
    ("db/q.sql", "SELECT 1; -- noqa: LT01\n"),
    ("lua/a.lua", "---@diagnostic disable-next-line: undefined-global\nx = 1\n"),
    ("lua/a.lua", "-- luacheck: ignore\n"),
    ("src/A.hs", "{-# LANGUAGE OverloadedStrings #-}\nmodule A where\n"),
    (
        "web/a.svelte",
        "<!-- svelte-ignore a11y-click-events-have-key-events -->\n<div/>\n",
    ),
    ("web/a.html", "<!-- prettier-ignore -->\n<p/>\n"),
    ("lib/a.ex", "# credo:disable-for-next-line\nx = 1\n"),
    ("lib/a.rb", "# frozen_string_literal: true\nx = 1\n"),
    ("lib/a.rb", "x = 1 # rubocop:disable Style/X\n"),
    ("lib/a.pl", "## no critic (ProhibitMagicNumbers)\n"),
    ("ps/a.ps1", "#Requires -Version 7\n"),
    ("r/a.r", "x <- 1 # nolint\n"),
    ("jl/a.jl", "#! format: off\n"),
    ("src/a.sol", "// SPDX-License-Identifier: MIT\n"),
    ("src/a.sol", "// solhint-disable-next-line\n"),
    ("api/a.proto", "// buf:lint:ignore FIELD_LOWER_SNAKE_CASE\n"),
    ("src/a.cpp", "int x; // NOLINTNEXTLINE(bugprone-x)\n"),
    ("src/a.ts", "// deno-lint-ignore no-explicit-any\n"),
    ("src/app.py", "# coding: utf-8\nx = 1\n"),
    ("pyproject.toml", "#:schema ./x.json\n"),
    ("web/a.css", "/* stylelint-disable-next-line */\na {}\n"),
    ("cmake/a.cmake", "# cmake-format: off\n"),
]

OUT_OF_SCOPE: list[str] = [
    "",
    "README.md",
    "package.json",
    ".env",
    ".env.local",
    "config/.env.production",
    "node_modules/x/a.js",
    "specs/plan/a.ts",
    "build/out.js",
    "pcb/board.kicad_pcb",
    "pcb/board.sch",
    "pcb/parts.lib",
    "pcb/board.pro",
    "art/palette.gpl",
    "rom/manifest.bml",
    "obj/main.d",
    "bin/tool",
    "proj/.venv/lib/a.py",
    "proj/lib/site-packages/x/a.py",
]


def family_for(path: str) -> CommentFamily:
    family = resolve_family(path)
    assert family is not None, path
    return family


def reported_numbers(pairs: list[tuple[int, str]]) -> tuple[int, ...]:
    return tuple(index + 1 for index, _ in pairs)


@pytest.mark.parametrize(("path", "content", "expected"), FLAGGED)
def test_reports_a_comment_in_every_family(
    path: str, content: str, expected: tuple[int, ...]
) -> None:
    # Arrange
    family = family_for(path)

    # Act
    pairs = comment_lines(content, family)

    # Assert
    assert reported_numbers(pairs) == expected


@pytest.mark.parametrize(("path", "content"), STRINGS_HOLDING_A_TOKEN)
def test_ignores_a_comment_token_inside_a_string(path: str, content: str) -> None:
    # Arrange
    family = family_for(path)

    # Act
    pairs = comment_lines(content, family)

    # Assert
    assert pairs == []


@pytest.mark.parametrize(("path", "content"), DIRECTIVES)
def test_allows_a_tool_directive_in_every_family(path: str, content: str) -> None:
    # Arrange
    family = family_for(path)

    # Act
    pairs = comment_lines(content, family)

    # Assert
    assert pairs == []


@pytest.mark.parametrize("path", OUT_OF_SCOPE)
def test_resolves_no_family_for_an_out_of_scope_path(path: str) -> None:
    # Arrange
    candidate = path

    # Act
    family = resolve_family(candidate)

    # Assert
    assert family is None


@pytest.mark.parametrize(
    ("path", "name"),
    [
        ("Dockerfile", "shell"),
        ("Makefile", "make"),
        ("makefile", "make"),
        ("Justfile", "just"),
        ("CMakeLists.txt", "cmake"),
        ("Vagrantfile", "ruby"),
        ("home/.bashrc", "shell"),
        ("src/A.TS", "javascript"),
        ("/abs/repo/src/a.py", "python"),
    ],
)
def test_resolves_a_family_by_basename_or_extension(path: str, name: str) -> None:
    # Arrange
    candidate = path

    # Act
    family = family_for(candidate)

    # Assert
    assert family.name == name


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/app.test.ts", True),
        ("src/app.spec.js", True),
        ("tests/test_x.py", True),
        ("pkg/x_test.py", True),
        ("pkg/x_test.go", True),
        ("src/__tests__/a.ts", True),
        ("/repo/tests/helpers.sh", True),
        ("e2e/flow.ts", True),
        ("scripts/run.bats", True),
        ("src/app.ts", False),
        ("src/latest.py", False),
        ("hooks/test-aaa-markers.py", False),
        ("src/contest_x.py", False),
    ],
)
def test_detects_a_test_path(path: str, expected: bool) -> None:
    # Arrange
    candidate = path

    # Act
    result = is_test_path(candidate)

    # Assert
    assert result is expected


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("tests/test_x.py", "def test_a():\n    # Arrange\n    x = 1\n"),
        ("src/a.test.ts", "// Act\nconst x = 1\n"),
        ("tests/q.sql", "-- Assert\nSELECT 1;\n"),
        ("tests/run.bats", '@test "a" {\n  # Arrange\n  true\n}\n'),
    ],
)
def test_allows_a_bare_marker_in_a_test_file(path: str, content: str) -> None:
    # Arrange
    family = family_for(path)

    # Act
    pairs = comment_lines(content, family, allow_aaa=True)

    # Assert
    assert pairs == []


@pytest.mark.parametrize(
    "content",
    [
        "# Assert: x\nx = 1\n",
        "# Act / Assert\nx = 1\n",
        "#Arrange\nx = 1\n",
        "x = 1  # Act\n",
        "# arrange\nx = 1\n",
    ],
)
def test_reports_a_marker_that_is_not_bare(content: str) -> None:
    # Arrange
    family = family_for("tests/test_x.py")

    # Act
    pairs = comment_lines(content, family, allow_aaa=True)

    # Assert
    assert reported_numbers(pairs) == (1,)


def test_reports_a_block_comment_marker() -> None:
    # Arrange
    family = family_for("src/a.test.ts")

    # Act
    pairs = comment_lines("/* Arrange */\nconst x = 1\n", family, allow_aaa=True)

    # Assert
    assert reported_numbers(pairs) == (1,)


def test_reports_a_bare_marker_outside_a_test_file() -> None:
    # Arrange
    family = family_for("src/app.py")

    # Act
    pairs = comment_lines("# Arrange\nx = 1\n", family)

    # Assert
    assert reported_numbers(pairs) == (1,)


def test_reports_only_the_docstring_an_edit_adds() -> None:
    # Arrange
    family = family_for("src/app.py")
    before = 'def f():\n    """Old."""\n    return 1\n\n\ndef g():\n    return 2\n'
    after = before.replace("    return 2\n", '    """New."""\n    return 2\n')

    # Act
    pairs = added_comment_lines(before, after, family)

    # Assert
    assert pairs == [(6, '"""New."""')]


def test_ignores_a_docstring_that_already_existed() -> None:
    # Arrange
    family = family_for("src/app.py")
    before = '"""Module."""\n\nx = 1\n'
    after = '"""Module."""\n\nx = 2\n'

    # Act
    pairs = added_comment_lines(before, after, family)

    # Assert
    assert pairs == []


def test_reports_a_string_statement_that_is_not_a_docstring_as_nothing() -> None:
    # Arrange
    family = family_for("src/app.py")

    # Act
    pairs = comment_lines('x = 1\n"""Not a docstring."""\n', family)

    # Assert
    assert pairs == []


def test_scans_python_that_does_not_parse() -> None:
    # Arrange
    family = family_for("src/app.py")

    # Act
    pairs = comment_lines("def f(:\n    # note\n", family)

    # Assert
    assert reported_numbers(pairs) == (2,)


def test_reports_a_second_copy_of_an_existing_comment() -> None:
    # Arrange
    family = family_for("src/app.py")

    # Act
    pairs = added_comment_lines("# note\nx = 1\n", "# note\nx = 1\n# note\n", family)

    # Assert
    assert pairs == [(2, "# note")]


def test_marks_a_hit_with_its_token_and_position() -> None:
    # Arrange
    family = family_for("src/a.ts")

    # Act
    hits = scan_hits("const a = 1 // tail\n// whole\n/* x\n y */\n", family)

    # Assert
    assert [
        (line, hit.token, hit.whole_line, hit.body) for line, hit in hits.items()
    ] == [
        (0, "//", False, "tail"),
        (1, "//", True, "whole"),
        (2, "/*", True, "x"),
        (3, "", False, None),
    ]


def test_masks_strings_and_comments_preserving_length_and_lines() -> None:
    # Arrange
    family = family_for("src/a.ts")
    text = 'const s = "{x}" // {y}\nconst t = 1\n'

    # Act
    masked = mask_code(text, family)

    # Assert
    assert masked == 'const s = "   "       \nconst t = 1\n'


def test_masks_a_region_family_document() -> None:
    # Arrange
    family = family_for("web/a.html")
    text = "<script>\nconst s = '}'\n</script>\n"

    # Act
    masked = mask_code(text, family)

    # Assert
    assert masked == "<script>\nconst s = ' '\n</script>\n"


def test_ignores_a_shebang_on_the_first_line() -> None:
    # Arrange
    family = family_for("scripts/run.sh")

    # Act
    pairs = comment_lines("#!/usr/bin/env bash\necho hi\n", family)

    # Assert
    assert pairs == []


def test_leaves_an_unterminated_block_comment_reported_to_the_end() -> None:
    # Arrange
    family = family_for("src/A.hs")

    # Act
    pairs = comment_lines("{- open\n{- nested\nx = 1\n", family)

    # Assert
    assert reported_numbers(pairs) == (1, 2, 3)


def test_ignores_a_heredoc_whose_terminator_never_appears() -> None:
    # Arrange
    family = family_for("scripts/a.sh")

    # Act
    pairs = comment_lines("cat <<EOF\n# real comment\n", family)

    # Assert
    assert reported_numbers(pairs) == (2,)


FAMILY_CASES: list[tuple[str, str, str, str]] = [
    ("fw/blink.ino", "// note\n", 'char *s = "// x";\n', "// NOLINTNEXTLINE\n"),
    (
        "gfx/a.glsl",
        "/* note */\n",
        'const char *s = "/* x */";\n',
        "// SPDX-License-Identifier: MIT\n",
    ),
    ("gfx/a.vert", "// note\n", "float a = 1.0;\n", "// clang-format off\n"),
    ("gfx/a.frag", "// note\n", "float a = 1.0;\n", "// clang-format off\n"),
    ("gfx/a.metal", "// note\n", "float a = 1.0;\n", "// clang-format off\n"),
    (
        "link/a.ld",
        "/* note */\n",
        'INCLUDE "a//b.ld"\n',
        "/* SPDX-License-Identifier: MIT */\n",
    ),
    (
        "link/a.lds",
        "/* note */\n",
        "SECTIONS { }\n",
        "/* SPDX-License-Identifier: MIT */\n",
    ),
    (
        "link/a.x",
        "/* note */\n",
        "SECTIONS { }\n",
        "/* SPDX-License-Identifier: MIT */\n",
    ),
    (
        "gal/a.pld",
        "/* note */\n",
        "PIN 1 = clk;\n",
        "/* SPDX-License-Identifier: MIT */\n",
    ),
    ("auto/Makefile.am", "# note\n", "X = a\\#b\n", "# SPDX-License-Identifier: MIT\n"),
    ("Makefile.arm9", "# note\n", "X = a\\#b\n", "# SPDX-License-Identifier: MIT\n"),
    (
        "docker/Dockerfile.dev",
        "# note\n",
        'RUN echo "# x"\n',
        "# hadolint ignore=DL3008\n",
    ),
    (
        "Procfile",
        "# note\n",
        "web: run --tag=a#b\n",
        "# SPDX-License-Identifier: MIT\n",
    ),
    ("BUILD", "# note\n", 'name = "# x"\n', "# buildifier: disable=load\n"),
    ("pkg/BUILD.bazel", "# note\n", 'name = "# x"\n', "# buildifier: disable=load\n"),
    ("WORKSPACE", "# note\n", 'name = "# x"\n', "# buildifier: disable=load\n"),
    ("tools/defs.bzl", "# note\n", 'name = "# x"\n', "# buildifier: disable=load\n"),
    ("meson.build", "# note\n", "x = '# y'\n", "# SPDX-License-Identifier: MIT\n"),
    (".gitignore", "# note\n", "dist/a#b\n", "# SPDX-License-Identifier: MIT\n"),
    (".dockerignore", "# note\n", "a#b\n", "# SPDX-License-Identifier: MIT\n"),
    (".prettierignore", "# note\n", "a#b\n", "# SPDX-License-Identifier: MIT\n"),
    (
        ".gitattributes",
        "# note\n",
        "*.a#b binary\n",
        "# SPDX-License-Identifier: MIT\n",
    ),
    (
        ".npmrc",
        "; note\n",
        "registry=https://x/#y\n",
        "# SPDX-License-Identifier: MIT\n",
    ),
    (
        ".shellcheckrc",
        "# note\n",
        "disable=SC2086\n",
        "# SPDX-License-Identifier: MIT\n",
    ),
    (".gdbinit", "# note\n", "set a#b\n", "# SPDX-License-Identifier: MIT\n"),
    ("dbg/run.gdb", "# note\n", "set a#b\n", "# SPDX-License-Identifier: MIT\n"),
    (
        "Doxyfile",
        "# note\n",
        "PROJECT_NAME = a#b\n",
        "# SPDX-License-Identifier: MIT\n",
    ),
    ("conf/a.tmux", "# note\n", "set -g a '#b'\n", "# shellcheck disable=SC2086\n"),
    ("src/a.coffee", "### note ###\n", 'x = "# y"\n', "# eslint-disable-line\n"),
    (
        "bi/a.lkml",
        "# note\n",
        'sql: ${TABLE}.a#b ;;\nlabel: "# x"\n',
        "# SPDX-License-Identifier: MIT\n",
    ),
    ("salt/a.sls", "{# note #}\n", "pkg: '# x'\n", "# yamllint disable-line\n"),
    ("tools/a.awk", "# note\n", 'print "# x"\n', "# SPDX-License-Identifier: MIT\n"),
    (
        "osx/a.applescript",
        "(* note *)\n",
        'set x to "-- y"\n',
        "-- SPDX-License-Identifier: MIT\n",
    ),
    (
        "osx/b.applescript",
        "# note\n",
        'set x to "# y"\n',
        "# SPDX-License-Identifier: MIT\n",
    ),
    ("doc/a.tex", "% note\n", "50\\% off\n", "% SPDX-License-Identifier: MIT\n"),
    ("doc/a.sty", "% note\n", "50\\% off\n", "% SPDX-License-Identifier: MIT\n"),
    ("doc/a.cls", "% note\n", "50\\% off\n", "% SPDX-License-Identifier: MIT\n"),
    (
        "doc/a.bib",
        "% note\n",
        "@book{a, title={50\\% off}}\n",
        "% SPDX-License-Identifier: MIT\n",
    ),
    ("mat/a.m", "% note\nx = 1;\n", "s = 'a % b'; y = A';\n", "%#ok<NASGU>\n"),
    ("mat/b.m", "%{\nnote\n%}\nx = 1;\n", 'x = "% y";\n', "%#ok<NASGU>\n"),
    (
        "objc/a.m",
        "#import <A.h>\n// note\n",
        '#import <A.h>\nNSString *s = @"// x";\n',
        "#import <A.h>\n// clang-format off\n",
    ),
    (
        "m4/a.m4",
        "dnl note\n",
        "define(`dnlx', 1)\n",
        "dnl SPDX-License-Identifier: MIT\n",
    ),
    (
        "configure.ac",
        "# note\n",
        "AC_INIT([a], [1])\n",
        "dnl SPDX-License-Identifier: MIT\n",
    ),
    (
        "vim/a.vim",
        '" note\n',
        'let s = "a" " trailing is ambiguous\n',
        '" vim: set ts=2:\n',
    ),
    (".vimrc", '" note\n', "set ts=2\n", '" vim: set ts=2:\n'),
    ("views/a.pug", "//- note\n", 'a(href="http://x") b\n', "//- prettier-ignore\n"),
    ("views/b.pug", "// note\n", "p http://x\n", "// prettier-ignore\n"),
    (
        "views/a.hbs",
        "{{!-- note --}}\n",
        "<p>{{a}} // x</p>\n",
        "{{!-- prettier-ignore --}}\n",
    ),
    (
        "views/b.handlebars",
        "{{! note }}\n",
        "<p>{{a}}</p>\n",
        "<!-- prettier-ignore -->\n",
    ),
    (
        "tpl/a.j2",
        "{# note #}\n",
        "a: '# x' // y\n",
        "{# SPDX-License-Identifier: MIT #}\n",
    ),
    (
        "tpl/a.jinja",
        "{# note #}\n",
        "{{ a }}\n",
        "{# SPDX-License-Identifier: MIT #}\n",
    ),
    (
        "views/a.ejs",
        "<%# note %>\n",
        "<p><%= a %> // x</p>\n",
        "<!-- prettier-ignore -->\n",
    ),
    (
        "tpl/a.tmpl",
        "{{/* note */}}\n",
        "// not a template comment\n",
        "{{/* SPDX-License-Identifier: MIT */}}\n",
    ),
    (
        "tpl/a.gotmpl",
        "{{- /* note */ -}}\n",
        "{{ .A }}\n",
        "{{/* SPDX-License-Identifier: MIT */}}\n",
    ),
    (
        "win/a.bat",
        "REM note\n",
        "echo a::b REMx\n",
        "REM SPDX-License-Identifier: MIT\n",
    ),
    (
        "win/a.cmd",
        ":: note\n",
        "echo rem is a word\n",
        ":: SPDX-License-Identifier: MIT\n",
    ),
    (
        "win/b.bat",
        "@rem note\n",
        "set REMOTE=1\n",
        "@rem SPDX-License-Identifier: MIT\n",
    ),
    (
        "asm/a.asm",
        "; note\n",
        "lda #$12\ncmp #';'\nex af,af'\n",
        "; SPDX-License-Identifier: MIT\n",
    ),
    (
        "asm/b.asm",
        "lda #1 // note\n",
        '!define a = "; x"\n',
        "; SPDX-License-Identifier: MIT\n",
    ),
    (
        "avr/a.S",
        "/* note */\n",
        "#include <avr/io.h>\nldi r16, 1\n",
        "; SPDX-License-Identifier: MIT\n",
    ),
    (
        "pic/a.s",
        "    movlw 1 ; note\n",
        "#define LED 1\n",
        "; SPDX-License-Identifier: MIT\n",
    ),
    (
        "m68k/a.s",
        "* note\n    move.l d0,d1\n",
        "    move.l #1,d0\n",
        "; SPDX-License-Identifier: MIT\n    move.l d0,d1\n",
    ),
    ("snes/a.a65", "; note\n", "lda #$12\n", "; SPDX-License-Identifier: MIT\n"),
    ("asm/a.inc", "; note\nLED = 1\n", "LED = 1\n", "; SPDX-License-Identifier: MIT\n"),
    (
        "c/a.inc",
        "#define A 1\n// note\n",
        '#define A "// x"\n',
        "#define A 1\n// NOLINTNEXTLINE\n",
    ),
]


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
    ("path", "flagged"), [(path, flagged) for path, flagged, _, _ in FAMILY_CASES]
)
def test_reports_a_comment_in_an_extended_family(path: str, flagged: str) -> None:
    # Arrange
    family = family_for_text(path, flagged)

    # Act
    pairs = comment_lines(flagged, family)

    # Assert
    assert len(pairs) >= 1


@pytest.mark.parametrize(
    ("path", "string"), [(path, string) for path, _, string, _ in FAMILY_CASES]
)
def test_ignores_a_token_inside_a_string_in_an_extended_family(
    path: str, string: str
) -> None:
    # Arrange
    family = family_for_text(path, string)

    # Act
    pairs = comment_lines(string, family)

    # Assert
    assert pairs == []


@pytest.mark.parametrize(
    ("path", "directive"), [(path, directive) for path, _, _, directive in FAMILY_CASES]
)
def test_allows_a_directive_in_an_extended_family(path: str, directive: str) -> None:
    # Arrange
    family = family_for_text(path, directive)

    # Act
    pairs = comment_lines(directive, family)

    # Assert
    assert pairs == []


def family_for_text(path: str, text: str) -> CommentFamily:
    family = resolve_family(path, text)
    assert family is not None, path
    return family


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

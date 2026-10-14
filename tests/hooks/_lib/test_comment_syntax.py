from __future__ import annotations


import pytest

from _helpers.comment_syntax_support import (
    comment_lines,
    family_for,
    is_test_path,
    reported_numbers,
    resolve_family,
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

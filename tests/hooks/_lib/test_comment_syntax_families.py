from __future__ import annotations


import pytest

from _helpers.comment_syntax_support import (
    CommentFamily,
    comment_lines,
    resolve_family,
)


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

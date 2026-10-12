from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Boundary(StrEnum):
    ANYWHERE = "anywhere"
    SPACED = "spaced"
    SHELL = "shell"
    FLOW = "flow"
    OPERAND = "operand"
    LINE_START = "line_start"
    COLUMN0 = "column0"
    EXPRESSION = "expression"


class Region(StrEnum):
    WHOLE = "whole"
    MARKUP = "markup"
    MAKE = "make"
    JUST = "just"
    YAML = "yaml"


class Premask(StrEnum):
    HEREDOC = "heredoc"
    YAML_BLOCK_SCALAR = "yaml_block_scalar"
    TEX_VERBATIM = "tex_verbatim"


@dataclass(frozen=True, slots=True)
class LineToken:
    token: str
    boundary: Boundary = Boundary.ANYWHERE
    rejected_before: str = ""
    rejected_after: str = ""
    requires_body: bool = False


@dataclass(frozen=True, slots=True)
class BlockToken:
    open: str
    close: str
    nests: bool = False
    column0: bool = False


@dataclass(frozen=True, slots=True)
class StringToken:
    open: str
    close: str
    escape: str = "\\"
    line_terminated: bool = False
    boundary: Boundary = Boundary.ANYWHERE
    doubled: bool = False
    interpolations: tuple[str, ...] = ()
    regex: bool = False


@dataclass(frozen=True, slots=True)
class CommentFamily:
    name: str
    lines: tuple[LineToken, ...] = ()
    blocks: tuple[BlockToken, ...] = ()
    strings: tuple[StringToken, ...] = ()
    shebang: bool = False
    premasks: tuple[Premask, ...] = ()
    region: Region = Region.WHOLE
    docstrings: bool = False
    doc_attribute: str = ""


def plain(quote: str, *, multiline: bool = False) -> StringToken:
    return StringToken(quote, quote, line_terminated=not multiline)


def verbatim(quote: str, *, multiline: bool = False) -> StringToken:
    return StringToken(quote, quote, escape="", line_terminated=not multiline)


LOWERCASE_LETTERS = "abcdefghijklmnopqrstuvwxyz"
C_BLOCK = BlockToken("/*", "*/")
SLASH_LINE = LineToken("//")
HASH_LINE = LineToken("#")
DASH_LINE = LineToken("--")
SEMICOLON_LINE = LineToken(";")
HASH_LINE_START = LineToken("#", Boundary.LINE_START)
SEMICOLON_LINE_START = LineToken(";", Boundary.LINE_START)
DOUBLE = plain('"')
SINGLE = plain("'")
TRIPLE_DOUBLE = plain('"""', multiline=True)
TRIPLE_SINGLE = plain("'''", multiline=True)
BACKTICK = plain("`", multiline=True)
TEMPLATE_LITERAL = StringToken("`", "`", interpolations=("${",))
INTERPOLATED_DOUBLE = StringToken('"', '"', interpolations=("${",))
PYTHON_STRINGS = (TRIPLE_DOUBLE, TRIPLE_SINGLE, DOUBLE, SINGLE)
HASKELL_SYMBOLS = "!#$%&*+./<=>?@\\^|~:"
BRACKET_LEVELS = ("", "=", "==", "===")

C = CommentFamily(
    "c",
    lines=(SLASH_LINE,),
    blocks=(C_BLOCK,),
    strings=(TRIPLE_DOUBLE, DOUBLE, SINGLE, BACKTICK),
)
JAVASCRIPT = CommentFamily(
    "javascript",
    lines=(SLASH_LINE,),
    blocks=(C_BLOCK,),
    strings=(
        DOUBLE,
        SINGLE,
        TEMPLATE_LITERAL,
        StringToken(
            "/", "/", line_terminated=True, boundary=Boundary.EXPRESSION, regex=True
        ),
    ),
)
RUST = CommentFamily(
    "rust",
    lines=(SLASH_LINE,),
    blocks=(BlockToken("/*", "*/", nests=True),),
    strings=(DOUBLE, SINGLE),
)
GROOVY = CommentFamily(
    "groovy",
    lines=(SLASH_LINE,),
    blocks=(C_BLOCK,),
    strings=(TRIPLE_DOUBLE, TRIPLE_SINGLE, INTERPOLATED_DOUBLE, SINGLE),
)
PHP = CommentFamily(
    "php",
    lines=(SLASH_LINE, LineToken("#", rejected_after="[")),
    blocks=(C_BLOCK,),
    strings=(DOUBLE, SINGLE, BACKTICK),
)
ZIG = CommentFamily(
    "zig",
    lines=(SLASH_LINE,),
    strings=(StringToken("\\\\", "\n", escape=""), DOUBLE, SINGLE),
)
SLASH_ONLY = CommentFamily("slash", lines=(SLASH_LINE,), strings=(DOUBLE,))
BLOCK_ONLY = CommentFamily("block", blocks=(C_BLOCK,), strings=(DOUBLE,))
CSS = CommentFamily("css", blocks=(C_BLOCK,), strings=(DOUBLE, SINGLE))
SCSS = CommentFamily(
    "scss",
    lines=(LineToken("//", rejected_before=":"),),
    blocks=(C_BLOCK,),
    strings=(DOUBLE, SINGLE),
)
PYTHON = CommentFamily(
    "python",
    lines=(HASH_LINE,),
    strings=PYTHON_STRINGS,
    shebang=True,
    docstrings=True,
)
STARLARK = CommentFamily("starlark", lines=(HASH_LINE,), strings=PYTHON_STRINGS)
SHELL = CommentFamily(
    "shell",
    lines=(LineToken("#", Boundary.SHELL),),
    strings=(
        StringToken('"', '"', interpolations=("$(", "${")),
        verbatim("'", multiline=True),
    ),
    shebang=True,
    premasks=(Premask.HEREDOC,),
)
RUBY = CommentFamily(
    "ruby",
    lines=(HASH_LINE,),
    blocks=(BlockToken("=begin", "=end", column0=True),),
    strings=(
        StringToken('"', '"', interpolations=("#{",)),
        plain("'", multiline=True),
        BACKTICK,
    ),
    shebang=True,
    premasks=(Premask.HEREDOC,),
)
PERL_POD_OPENERS = (
    "=pod",
    "=head1",
    "=head2",
    "=head3",
    "=head4",
    "=begin",
    "=over",
    "=item",
    "=for",
    "=encoding",
)
PERL = CommentFamily(
    "perl",
    lines=(LineToken("#", rejected_before="$"),),
    blocks=tuple(
        BlockToken(opener, "=cut", column0=True) for opener in PERL_POD_OPENERS
    ),
    strings=(plain('"', multiline=True), plain("'", multiline=True)),
    shebang=True,
    premasks=(Premask.HEREDOC,),
)
POWERSHELL = CommentFamily(
    "powershell",
    lines=(HASH_LINE,),
    blocks=(BlockToken("<#", "#>"),),
    strings=(
        StringToken('@"', '"@', escape=""),
        StringToken("@'", "'@", escape=""),
        StringToken('"', '"', escape="`"),
        verbatim("'", multiline=True),
    ),
)
YAML_STRINGS = (
    StringToken('"', '"', boundary=Boundary.FLOW),
    StringToken("'", "'", escape="", boundary=Boundary.FLOW, doubled=True),
)
YAML = CommentFamily(
    "yaml",
    lines=(LineToken("#", Boundary.SPACED),),
    strings=YAML_STRINGS,
    premasks=(Premask.YAML_BLOCK_SCALAR,),
    region=Region.YAML,
)
SALT = CommentFamily(
    "salt",
    lines=(LineToken("#", Boundary.SPACED),),
    blocks=(BlockToken("{#", "#}"),),
    strings=YAML_STRINGS,
    premasks=(Premask.YAML_BLOCK_SCALAR,),
)
TOML = CommentFamily(
    "toml",
    lines=(HASH_LINE,),
    strings=(TRIPLE_DOUBLE, verbatim("'''", multiline=True), DOUBLE, verbatim("'")),
)
MAKE = CommentFamily(
    "make", lines=(LineToken("#", rejected_before="\\"),), region=Region.MAKE
)
JUST = CommentFamily(
    "just", lines=(HASH_LINE,), strings=(DOUBLE, SINGLE), region=Region.JUST
)
HCL = CommentFamily(
    "hcl",
    lines=(HASH_LINE, SLASH_LINE),
    blocks=(C_BLOCK,),
    strings=(StringToken('"', '"', interpolations=("${", "%{")),),
    premasks=(Premask.HEREDOC,),
)
HASH_LINE_ONLY = CommentFamily("hash_line", lines=(HASH_LINE_START,))
INI = CommentFamily("ini", lines=(HASH_LINE_START, SEMICOLON_LINE_START))
PROPERTIES = CommentFamily(
    "properties", lines=(HASH_LINE_START, LineToken("!", Boundary.LINE_START))
)
CMAKE = CommentFamily(
    "cmake",
    lines=(HASH_LINE,),
    blocks=tuple(BlockToken(f"#[{level}[", f"]{level}]") for level in BRACKET_LEVELS),
    strings=(plain('"', multiline=True),),
)
COFFEE = CommentFamily(
    "coffee",
    lines=(HASH_LINE,),
    blocks=(BlockToken("###", "###"),),
    strings=(TRIPLE_DOUBLE, TRIPLE_SINGLE, DOUBLE, SINGLE),
)
GRAPHQL = CommentFamily("graphql", lines=(HASH_LINE,), strings=(TRIPLE_DOUBLE, DOUBLE))
NIX = CommentFamily(
    "nix",
    lines=(HASH_LINE,),
    blocks=(C_BLOCK,),
    strings=(StringToken("''", "''", escape=""), plain('"', multiline=True)),
)
R_LANG = CommentFamily(
    "r",
    lines=(HASH_LINE,),
    strings=(plain('"', multiline=True), plain("'", multiline=True)),
)
JULIA = CommentFamily(
    "julia",
    lines=(HASH_LINE,),
    blocks=(BlockToken("#=", "=#", nests=True),),
    strings=(TRIPLE_DOUBLE, plain('"', multiline=True)),
)
ELIXIR = CommentFamily(
    "elixir",
    lines=(LineToken("#", rejected_before="?"),),
    strings=(TRIPLE_DOUBLE, TRIPLE_SINGLE, plain('"', multiline=True), SINGLE),
    doc_attribute=r"^\s*@(?:moduledoc|doc|typedoc)\b(?!\s+false\b)",
)
CRYSTAL = CommentFamily("crystal", lines=(HASH_LINE,), strings=(DOUBLE, SINGLE))
NIM = CommentFamily(
    "nim",
    lines=(HASH_LINE,),
    blocks=(BlockToken("#[", "]#", nests=True),),
    strings=(verbatim('"""', multiline=True), DOUBLE, SINGLE),
)
AWK = CommentFamily("awk", lines=(HASH_LINE,), strings=(DOUBLE,))
LOOKML = CommentFamily(
    "lookml", lines=(LineToken("#", Boundary.SPACED),), strings=(DOUBLE,)
)
SQL = CommentFamily(
    "sql",
    lines=(DASH_LINE,),
    blocks=(C_BLOCK,),
    strings=(
        StringToken("$$", "$$", escape=""),
        StringToken("'", "'", escape="", doubled=True),
        StringToken('"', '"', escape="", doubled=True),
        verbatim("`", multiline=True),
    ),
)
LUA = CommentFamily(
    "lua",
    lines=(DASH_LINE,),
    blocks=tuple(BlockToken(f"--[{level}[", f"]{level}]") for level in BRACKET_LEVELS),
    strings=(DOUBLE, SINGLE)
    + tuple(
        StringToken(f"[{level}[", f"]{level}]", escape="") for level in BRACKET_LEVELS
    ),
)
HASKELL = CommentFamily(
    "haskell",
    lines=(LineToken("--", rejected_after=HASKELL_SYMBOLS),),
    blocks=(BlockToken("{-", "-}", nests=True),),
    strings=(TRIPLE_DOUBLE, DOUBLE),
)
APPLESCRIPT = CommentFamily(
    "applescript",
    lines=(DASH_LINE, HASH_LINE),
    blocks=(BlockToken("(*", "*)", nests=True),),
    strings=(DOUBLE,),
    shebang=True,
)
OCAML = CommentFamily(
    "ocaml", blocks=(BlockToken("(*", "*)", nests=True),), strings=(DOUBLE,)
)
LISP = CommentFamily(
    "lisp",
    lines=(LineToken(";", rejected_before="\\?"),),
    blocks=(BlockToken("#|", "|#", nests=True),),
    strings=(plain('"', multiline=True),),
)
TEX = CommentFamily(
    "tex",
    lines=(LineToken("%", rejected_before="\\", requires_body=True),),
    premasks=(Premask.TEX_VERBATIM,),
)
ERLANG = CommentFamily(
    "erlang",
    lines=(LineToken("%", rejected_before="$"),),
    strings=(plain('"', multiline=True), SINGLE),
    doc_attribute=r"^\s*-(?:moduledoc|doc)\b",
)
MATLAB = CommentFamily(
    "matlab",
    lines=(LineToken("%"),),
    blocks=(BlockToken("%{", "%}", column0=True),),
    strings=(
        DOUBLE,
        StringToken(
            "'", "'", escape="", line_terminated=True, boundary=Boundary.OPERAND
        ),
    ),
)
M4 = CommentFamily(
    "m4",
    lines=(
        LineToken("dnl", Boundary.SPACED, rejected_after=LOWERCASE_LETTERS + "_"),
        HASH_LINE,
    ),
)
VIM = CommentFamily(
    "vim",
    lines=(LineToken('"', Boundary.LINE_START),),
    strings=(verbatim("'"), plain('"')),
)
BATCH = CommentFamily(
    "batch",
    lines=tuple(
        LineToken(token, Boundary.LINE_START, rejected_after=LOWERCASE_LETTERS)
        for token in ("REM", "rem", "Rem", "@REM", "@rem", "::")
    ),
)
ASM_CHAR = StringToken(
    "'", "'", escape="", line_terminated=True, boundary=Boundary.OPERAND
)
ASSEMBLY = CommentFamily(
    "assembly",
    lines=(SEMICOLON_LINE, SLASH_LINE),
    blocks=(C_BLOCK,),
    strings=(DOUBLE, ASM_CHAR),
)
ASSEMBLY_68K = CommentFamily(
    "assembly_68k",
    lines=(SEMICOLON_LINE, LineToken("*", Boundary.COLUMN0)),
    blocks=(C_BLOCK,),
    strings=(DOUBLE, ASM_CHAR),
)
MARKUP = CommentFamily(
    "markup", blocks=(BlockToken("<!--", "-->"),), region=Region.MARKUP
)
HANDLEBARS = CommentFamily(
    "handlebars",
    blocks=(
        BlockToken("{{!--", "--}}"),
        BlockToken("{{!", "}}"),
        BlockToken("<!--", "-->"),
    ),
    region=Region.MARKUP,
)
EJS = CommentFamily(
    "ejs",
    blocks=(BlockToken("<%#", "%>"), BlockToken("<!--", "-->")),
    region=Region.MARKUP,
)
PUG = CommentFamily(
    "pug",
    lines=(LineToken("//-", Boundary.LINE_START), LineToken("//", Boundary.LINE_START)),
)
JINJA = CommentFamily("jinja", blocks=(BlockToken("{#", "#}"),))
GO_TEMPLATE = CommentFamily(
    "go_template",
    blocks=(BlockToken("{{/*", "*/}}"), BlockToken("{{- /*", "*/ -}}")),
)

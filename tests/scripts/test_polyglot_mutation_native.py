from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.guard_runner import Edit  # noqa: E402
from _lib.polyglot_mutation_native import NATIVE_FINDERS  # noqa: E402

BLOCKED: list[tuple[str, str, str]] = [
    (
        "go-package-var",
        "main.go",
        'import "net/http"\n\nfunc init() {\n\thttp.DefaultClient = nil\n}\n',
        "reassigns `http.DefaultClient`",
    ),
    (
        "go-shared-map",
        "cache.go",
        "var seen = map[string]bool{}\n\nfunc mark(id string) {\n\tseen[id] = true\n}\n",
        "package-level `seen` is mutated",
    ),
    (
        "go-shared-slice-append",
        "log.go",
        "var (\n\tentries []string\n)\n\nfunc add(e string) {\n\tentries = append(entries, e)\n}\n",
        "package-level `entries` is mutated",
    ),
    ("rust-static-mut", "lib.rs", "static mut COUNTER: u32 = 0;\n", "`static mut`"),
    (
        "c-mutable-table",
        "tables.c",
        "static u16 palette[4] = {0x0000, 0x7fff, 0x001f, 0x03e0};\n",
        "file-scope table `palette`",
    ),
    (
        "cpp-mutable-vector",
        "tables.cpp",
        "std::vector<int> primes = {2, 3, 5};\n",
        "file-scope table `primes`",
    ),
]

ADVISORY: list[tuple[str, str, str]] = [
    (
        "go-append-assign",
        "a.go",
        "func f(base []int) {\n\tout = append(base, 1)\n}\n",
        "append",
    ),
    (
        "rust-refcell",
        "a.rs",
        "struct S { cache: RefCell<Vec<u8>> }\n",
        "interior mutability",
    ),
    (
        "swift-static-var",
        "a.swift",
        "struct Config {\n    static var shared = Config()\n}\n",
        "static var",
    ),
]

ALLOWED: list[tuple[str, str, str]] = [
    ("go-struct-field", "a.go", "func (s *Server) stop() {\n\ts.running = false\n}\n"),
    (
        "go-local-map",
        "a.go",
        'func f() map[string]int {\n\tm := map[string]int{}\n\tm["a"] = 1\n\treturn m\n}\n',
    ),
    ("go-err-sentinel", "a.go", 'var ErrNotFound = errors.New("not found")\n'),
    ("rust-static", "a.rs", "static LIMIT: u32 = 10;\n"),
    ("c-const-table", "a.c", "static const u16 palette[4] = {0, 1, 2, 3};\n"),
    ("c-volatile-register", "a.h", "volatile u16 *regs[2] = {REG_A, REG_B};\n"),
    ("c-zero-buffer", "a.c", "u8 frame[256] = {0};\n"),
    ("c-local-array", "a.c", "void f(void) {\n    int scratch[2] = {1, 2};\n}\n"),
    ("c-comment", "a.c", "/* u8 table[2] = {1, 2}; */\n"),
]


def _run(path: str, text: str):
    finder = NATIVE_FINDERS[Path(path).suffix]
    return finder(Edit(path=f"/repo/{path}", text=text, full_file=True))


@pytest.mark.parametrize(("label", "path", "text", "expected"), BLOCKED)
def test_blocks(label, path, text, expected):
    # Arrange
    source = text

    # Act
    hits = _run(path, source)

    # Assert
    assert [(hit.blocking, expected in hit.message) for hit in hits] == [
        (True, True)
    ], label


@pytest.mark.parametrize(("label", "path", "text", "expected"), ADVISORY)
def test_advises(label, path, text, expected):
    # Arrange
    source = text

    # Act
    hits = _run(path, source)

    # Assert
    assert [(hit.blocking, expected in hit.message) for hit in hits] == [
        (False, True)
    ], label


@pytest.mark.parametrize(("label", "path", "text"), ALLOWED)
def test_allows(label, path, text):
    # Arrange
    source = text

    # Act
    hits = _run(path, source)

    # Assert
    assert hits == (), label


def test_go_block_imports_resolve_aliases_and_versioned_paths():
    # Arrange
    text = (
        "import (\n"
        '\t_ "embed"\n'
        '\tredisv9 "github.com/redis/go-redis/v9"\n'
        '\t"example.com/cfg/v2"\n'
        ")\n"
        "\n"
        "func init() {\n"
        "\tredisv9.Nil = nil\n"
        "\tcfg.Default = 1\n"
        "}\n"
    )

    # Act
    hits = _run("main.go", text)

    # Assert
    assert [(hit.line, hit.blocking) for hit in hits] == [(8, True), (9, True)]


def test_go_reading_a_shared_map_is_not_a_write():
    # Arrange
    text = "var seen = map[string]bool{}\n\nfunc has(id string) bool {\n\treturn seen[id]\n}\n"

    # Act
    hits = _run("a.go", text)

    # Assert
    assert hits == ()

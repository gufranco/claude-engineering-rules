from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.analyzer_runs import ANALYZERS, run

FIXTURES: dict[str, tuple[str, str]] = {
    "c": (
        "a.cpp",
        (
            "int counter = 0;\n"
            "int sum(int *values, int n) { int total = 0; for (int i = 0; i < n; i++) total += values[i]; return total; }\n"
            "void strip(const int *p) { int *q = const_cast<int *>(p); *q = 0; }\n"
            "struct S { int v; int get() { return v; } };\n"
        ),
    ),
    "go": (
        "a.go",
        (
            "package probe\n"
            "\n"
            'import "net/http"\n'
            "\n"
            "var seen = map[string]bool{}\n"
            "\n"
            "type Counter struct{ n int }\n"
            "\n"
            "func (c Counter) Inc() { c.n++ }\n"
            "\n"
            "func mark(id string, ids []string) []string {\n"
            "\tseen[id] = true\n"
            "\tout := []string{}\n"
            "\tout = append(ids, id)\n"
            "\thttp.DefaultClient = nil\n"
            "\treturn out\n"
            "}\n"
        ),
    ),
    "python-ruff": (
        "a.py",
        (
            "import dataclasses\n"
            "import time\n"
            "\n"
            "COUNT = 0\n"
            "\n"
            "def bump():\n"
            "    global COUNT\n"
            "    COUNT = COUNT + 1\n"
            "\n"
            "def peek():\n"
            "    global COUNT\n"
            "    return COUNT\n"
            "\n"
            "def collect(items=[], at=time.time()):\n"
            "    for item in items:\n"
            "        items.append(item)\n"
            "    return items\n"
            "\n"
            "def shadow(x):\n"
            "    for x in x:\n"
            "        print(x)\n"
            "\n"
            "def loop(rows):\n"
            "    for row in rows:\n"
            "        row = row.strip()\n"
            "        print(row)\n"
            "\n"
            "class Registry:\n"
            "    handlers: list[str] = []\n"
            "\n"
            "    def reset(self):\n"
            "        self = None\n"
            "\n"
            "@dataclasses.dataclass\n"
            "class P:\n"
            "    tags: list = []\n"
            "    at: list[int] = list(range(3))\n"
        ),
    ),
    "python-pyright": (
        "a.py",
        ("MAX_SIZE = 10\nMAX_SIZE = 11\n"),
    ),
    "ruby": (
        "a.rb",
        ("ROLES = [:a, :b]\n$count = 0\nclass A\n  @@seen = []\nend\n"),
    ),
    "lua": (
        "a.lua",
        (
            "local count = 0\n"
            "function bump(step)\n"
            "  total = count + step\n"
            "end\n"
            "undefined_table.field = 1\n"
            "print = nil\n"
            "math.pi = 3\n"
            "string.trim = nil\n"
        ),
    ),
    "kotlin": (
        "A.kt",
        ("data class User(val id: String, var name: String)\n"),
    ),
    "java": (
        "A.java",
        (
            "public class A {\n"
            "    public static int count = 0;\n"
            "    private int size;\n"
            "    private final int[] data;\n"
            "    A(int[] d, int s) { this.data = d; this.size = s; count = s; }\n"
            "    int[] data() { return data; }\n"
            "    int grow(int n) { n = n + 1; return n + size; }\n"
            "}\n"
        ),
    ),
    "swift": (
        "a.swift",
        ("var counter = 0\nstruct Config {\n    static var shared = Config()\n}\n"),
    ),
    "dart": (
        "a.dart",
        (
            "class Box {\n"
            "  int _size = 1;\n"
            "  int area(List<int> xs) {\n"
            "    var w = 2;\n"
            "    var factor = 3;\n"
            "    for (var x in xs) {\n"
            "      w += x;\n"
            "    }\n"
            "    return w * _size * factor;\n"
            "  }\n"
            "}\n"
        ),
    ),
}


def _expected(key: str) -> frozenset[str]:
    analyzer = ANALYZERS[key]
    return analyzer.blocking | analyzer.advisory


@pytest.mark.parametrize("key", sorted(ANALYZERS))
def test_every_catalog_rule_fires_on_its_fixture(tmp_path, key):
    # Arrange
    name, text = FIXTURES[key]
    source = tmp_path / name
    source.write_text(text, encoding="utf-8")
    (tmp_path / "go.mod").write_text(
        "module example.com/probe\n\ngo 1.22\n", encoding="utf-8"
    )

    # Act
    result = run(ANALYZERS[key], source)

    # Assert
    fired = frozenset(f.rule for f in result.findings)
    assert (result.failure, _expected(key) - fired) == ("", frozenset())

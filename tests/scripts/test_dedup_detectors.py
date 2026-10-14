from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.dedup_detectors import find, is_dedup_source  # noqa: E402

FLAGGED: list[tuple[str, str, str]] = [
    (
        "a.ts",
        "const processedIds = new Set<string>();\nfunction f(id: string) {\n  if (processedIds.has(id)) return;\n  processedIds.add(id);\n}\n",
        "processedIds",
    ),
    (
        "a.py",
        "seen: set[str] = set()\n\ndef handle(e):\n    if e.id in seen:\n        return\n    seen.add(e.id)\n",
        "seen",
    ),
    (
        "a.go",
        "var handled = map[string]bool{}\n\nfunc consume(id string) {\n\tif handled[id] {\n\t\treturn\n\t}\n\thandled[id] = true\n}\n",
        "handled",
    ),
    (
        "a.go",
        "var delivered sync.Map\n\nfunc f(id string) {\n\tdelivered.LoadOrStore(id, true)\n}\n",
        "delivered",
    ),
    (
        "A.java",
        "class C {\n    private static final Set<String> processed = ConcurrentHashMap.newKeySet();\n    void f(String id) { if (!processed.add(id)) return; }\n}\n",
        "processed",
    ),
    (
        "A.kt",
        "class C {\n    private val seenIds = mutableSetOf<String>()\n    fun f(id: String) { if (!seenIds.add(id)) return }\n}\n",
        "seenIds",
    ),
    (
        "A.cs",
        "class C\n{\n    private static readonly HashSet<string> _handled = new();\n    void F(string id) { if (!_handled.Add(id)) return; }\n}\n",
        "_handled",
    ),
    (
        "a.rb",
        "PROCESSED = Set.new\n\ndef call(id)\n  return if PROCESSED.include?(id)\n  PROCESSED << id\nend\n",
        "PROCESSED",
    ),
    (
        "a.dart",
        "final Set<String> sentIds = {};\n\nvoid send(String id) {\n  if (!sentIds.add(id)) return;\n}\n",
        "sentIds",
    ),
    (
        "a.ex",
        "def init(_), do: :ets.new(:processed_events, [:set, :named_table])\ndef seen?(id), do: :ets.insert_new(:processed_events, {id})\n",
        "processed_events",
    ),
    (
        "a.clj",
        "(def seen-ids (atom #{}))\n(defn handle [id] (when-not (contains? @seen-ids id) (swap! seen-ids conj id)))\n",
        "seen-ids",
    ),
]

CLEAN: list[tuple[str, str]] = [
    (
        "a.ts",
        "function unique(xs: string[]) {\n  const seen = new Set<string>();\n  return xs.filter((x) => !seen.has(x) && seen.add(x));\n}\n",
    ),
    (
        "a.go",
        "func dedupe(xs []string) []string {\n\tseen := map[string]bool{}\n\tfor _, x := range xs {\n\t\tseen[x] = true\n\t}\n\treturn nil\n}\n",
    ),
    (
        "A.java",
        "class C {\n    void f(List<String> xs) {\n        Set<String> seen = new HashSet<>();\n        seen.addAll(xs);\n    }\n}\n",
    ),
    (
        "a.ts",
        "const inflightRequests = new Map<string, Promise<void>>();\nexport const get = (k: string) => inflightRequests.get(k);\n",
    ),
    ("a.py", "processed = redis.Redis()\n"),
]


@pytest.mark.parametrize(("path", "text", "name"), FLAGGED)
def test_flags_in_memory_dedup_store(path, text, name):
    # Arrange
    source = text

    # Act
    hits = find(path, source)

    # Assert
    assert [name in hit.message for hit in hits] == [True], path


@pytest.mark.parametrize(("path", "text"), CLEAN)
def test_ignores_local_or_durable_state(path, text):
    # Arrange
    source = text

    # Act
    hits = find(path, source)

    # Assert
    assert hits == (), path


def test_is_dedup_source_skips_tests_and_scratch():
    # Arrange
    paths = (
        "/repo/src/a.go",
        "/repo/src/a_test.go",
        "/repo/src/a.test.ts",
        "/repo/docs/a.md",
        "/repo/lib/a_spec.rb",
    )

    # Act
    verdicts = tuple(is_dedup_source(path) for path in paths)

    # Assert
    assert verdicts == (True, False, False, False, False)

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.guard_runner import Edit  # noqa: E402
from _lib.polyglot_mutation_jvm import JVM_FINDERS  # noqa: E402

BLOCKED: list[tuple[str, str, str]] = [
    (
        "java-static",
        "A.java",
        "class A {\n    public static int count = 0;\n}\n",
        "static field `count`",
    ),
    (
        "java-static-collection",
        "A.java",
        "class A {\n    private static final List<String> NAMES = new ArrayList<>();\n}\n",
        "`NAMES` is a mutable collection",
    ),
    (
        "kotlin-data-var",
        "A.kt",
        "data class User(val id: String, var name: String)\n",
        "data class `User`",
    ),
    (
        "kotlin-mutable-signature",
        "A.kt",
        "fun tags(): MutableList<String> = mutableListOf()\n",
        "`MutableList`",
    ),
    (
        "csharp-record-struct",
        "A.cs",
        "public record struct Point(int X, int Y);\n",
        "`readonly record struct`",
    ),
    (
        "csharp-record-setter",
        "A.cs",
        "public record User\n{\n    public string Name { get; set; }\n}\n",
        "record `User`",
    ),
    (
        "csharp-static",
        "A.cs",
        "public class A\n{\n    public static int Count = 0;\n}\n",
        "static field `Count`",
    ),
    (
        "dart-widget-field",
        "a.dart",
        "class Card extends StatelessWidget {\n  String title;\n  Card(this.title);\n}\n",
        "`title` in immutable class `Card`",
    ),
    (
        "dart-unfreezed",
        "a.dart",
        "@unfreezed\nclass Draft with _$Draft {}\n",
        "`@unfreezed`",
    ),
]

ADVISORY: list[tuple[str, str, str]] = [
    (
        "java-unmodifiable-view",
        "A.java",
        "class A {\n    A(List<String> xs) { this.xs = Collections.unmodifiableList(xs); }\n}\n",
        "live view",
    ),
    (
        "csharp-collection-setter",
        "A.cs",
        "public class Dto\n{\n    public List<string> Tags { get; set; }\n}\n",
        "`Tags`",
    ),
]

ALLOWED: list[tuple[str, str, str]] = [
    ("java-constant", "A.java", "class A {\n    public static final int MAX = 3;\n}\n"),
    (
        "java-static-method",
        "A.java",
        "class A {\n    public static int add(int a) { return a; }\n}\n",
    ),
    (
        "java-immutable-list",
        "A.java",
        'class A {\n    static final List<String> N = List.of("a");\n}\n',
    ),
    ("kotlin-data-val", "A.kt", "data class User(val id: String, val name: String)\n"),
    (
        "kotlin-private-mutable",
        "A.kt",
        "private val cache: MutableMap<String, Int> = mutableMapOf()\n",
    ),
    (
        "csharp-readonly-record-struct",
        "A.cs",
        "public readonly record struct Point(int X, int Y);\n",
    ),
    (
        "csharp-init",
        "A.cs",
        "public record User\n{\n    public string Name { get; init; }\n}\n",
    ),
    (
        "csharp-static-readonly",
        "A.cs",
        "public class A\n{\n    public static readonly int Max = 3;\n}\n",
    ),
    (
        "dart-final-field",
        "a.dart",
        "class Card extends StatelessWidget {\n  final String title;\n  const Card(this.title);\n}\n",
    ),
    (
        "dart-state-class",
        "a.dart",
        "class _CardState extends State<Card> {\n  int count = 0;\n}\n",
    ),
]


def _run(path: str, text: str):
    return JVM_FINDERS[Path(path).suffix](
        Edit(path=f"/repo/{path}", text=text, full_file=True)
    )


@pytest.mark.parametrize(("label", "path", "text", "expected"), BLOCKED)
def test_blocks(label, path, text, expected):
    # Arrange
    source = text

    # Act
    hits = _run(path, source)

    # Assert
    assert [(hit.blocking, expected in hit.message) for hit in hits] == [
        (True, True)
    ], (label, hits)


@pytest.mark.parametrize(("label", "path", "text", "expected"), ADVISORY)
def test_advises(label, path, text, expected):
    # Arrange
    source = text

    # Act
    hits = _run(path, source)

    # Assert
    assert [(hit.blocking, expected in hit.message) for hit in hits] == [
        (False, True)
    ], (label, hits)


@pytest.mark.parametrize(("label", "path", "text"), ALLOWED)
def test_allows(label, path, text):
    # Arrange
    source = text

    # Act
    hits = _run(path, source)

    # Assert
    assert hits == (), label


def test_kotlin_data_class_fragment_without_closing_paren():
    # Arrange
    text = "data class User(\n    var name: String,\n"

    # Act
    hits = _run("A.kt", text)

    # Assert
    assert [(hit.line, hit.blocking) for hit in hits] == [(1, True)]


def test_dart_immutable_annotation_marks_the_class():
    # Arrange
    text = "@immutable\nclass Money {\n  int cents;\n}\n"

    # Act
    hits = _run("a.dart", text)

    # Assert
    assert ["`cents` in immutable class `Money`" in hit.message for hit in hits] == [
        True
    ]


def test_kotlin_local_with_inferred_mutable_type_is_not_public_api():
    # Arrange
    text = "fun main() {\n    val counts = HashMap<String, Int>()\n}\n"

    # Act
    hits = _run("A.kt", text)

    # Assert
    assert hits == ()

from __future__ import annotations

SKIP_SEGMENTS = (
    "/test/",
    "/tests/",
    "/spec/",
    "/__tests__/",
    "/testdata/",
    "/fixtures/",
    "/vendor/",
    "/node_modules/",
    "/third_party/",
    "/external/",
    "/build/",
    "/.dart_tool/",
    "/target/",
    "/bin/",
    "/obj/",
    "/.claude/hooks/",
    "/site-packages/",
)
SKIP_SUFFIXES = (
    "_test.go",
    ".pb.go",
    "_gen.go",
    "test.java",
    "tests.java",
    "test.kt",
    "tests.kt",
    "tests.cs",
    "test.cs",
    ".g.dart",
    ".freezed.dart",
    "_test.dart",
    "_spec.rb",
    "_test.rb",
    ".g.cs",
    ".designer.cs",
    "_spec.lua",
    "_test.lua",
    "_test.py",
    "_tests.py",
    ".test.py",
    "/conftest.py",
    ".pyi",
)
SKIP_PREFIXES = ("test_",)


def in_scope(path: str) -> bool:
    lowered = path.lower()
    if lowered.endswith(SKIP_SUFFIXES):
        return False
    if any(segment in lowered for segment in SKIP_SEGMENTS):
        return False
    return not lowered.rsplit("/", 1)[-1].startswith(SKIP_PREFIXES)

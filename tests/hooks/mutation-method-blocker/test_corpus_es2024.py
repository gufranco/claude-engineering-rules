"""ES2024+ replacement corpus regression.

Item 175 of the plan. Loads `tests/corpus/mutation-method-blocker/
es2024_replacements/clean.ts` and asserts the hook returns exit 0 with no
detector hits. Catches false positives whenever new ES2024+ patterns are
introduced (Set composition, iterator helpers, Object.groupBy, Map.groupBy,
Promise.withResolvers, Promise.try, Array.fromAsync, RegExp.escape,
Atomics.pause, Error.isError, Float16Array allocation, spread-based copies).
"""

from __future__ import annotations

from pathlib import Path

from conftest import REPO_ROOT, assert_allows, run_hook_subprocess

CORPUS_FILE = (
    REPO_ROOT
    / "tests"
    / "corpus"
    / "mutation-method-blocker"
    / "es2024_replacements"
    / "clean.ts"
)


def test_es2024_clean_corpus_passes(hook_path: Path) -> None:
    # Arrange
    content = CORPUS_FILE.read_text(encoding="utf-8")
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/es2024_replacements_clean.ts",
            "content": content,
        },
    }

    # Act
    code, stdout, stderr = run_hook_subprocess(hook_path, payload)

    # Assert
    assert_allows(code, stdout, stderr)

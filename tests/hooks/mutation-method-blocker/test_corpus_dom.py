from __future__ import annotations

from pathlib import Path

from conftest import REPO_ROOT, assert_plain_allow, run_hook_subprocess

CORPUS_FILE = (
    REPO_ROOT / "tests" / "corpus" / "mutation-method-blocker" / "dom" / "clean.ts"
)


def test_dom_clean_corpus_passes(hook_path: Path) -> None:
    # Arrange
    content = CORPUS_FILE.read_text(encoding="utf-8")
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/dom_clean.ts",
            "content": content,
        },
    }

    # Act
    code, stdout, stderr = run_hook_subprocess(hook_path, payload)

    # Assert
    assert_plain_allow(code, stdout, stderr)

"""DOM and Web API allowance corpus regression.

Item 199 of the plan. Loads `tests/corpus/mutation-method-blocker/dom/
clean.ts` and asserts the hook returns exit 0 with no detector hits. Pins
the DOM-aware property assignment policy: document/body/element property
writes, .style.* writes, .dataset.* writes, scrollTop/scrollLeft compound
assignment, typed-suffix receivers (myButton, submitBtn, inputRef,
canvasEl, linkEl, imgEl), and event.target / event.currentTarget chains
are all silently allowed. The global mutation detector remains in scope
and is exercised separately.
"""

from __future__ import annotations

from pathlib import Path

from conftest import REPO_ROOT, assert_allows, run_hook_subprocess

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
    assert_allows(code, stdout, stderr)

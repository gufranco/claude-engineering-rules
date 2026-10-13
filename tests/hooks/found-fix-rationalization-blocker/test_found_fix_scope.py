from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "found-fix-rationalization-blocker"


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("/repo/src/board.tsx", 'export const CTA = "Create a new task";\n'),
        ("/repo/app/tracker.py", 'HINT = "Opened a ticket"\n'),
        (
            "/private/tmp/claude-501/project/session/scratchpad/notes.md",
            "Will fix this in a follow-up PR.\n",
        ),
    ],
)
def test_product_strings_and_scratch_notes_are_not_scanned(
    tool_use, run_hook, path, content
):
    # Arrange
    payload = tool_use("Write", {"file_path": path, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("/repo/src/board.tsx", "// will fix this in a follow-up PR\nconst a = 1;\n"),
        ("/repo/NOTES.md", "Will fix this in a follow-up PR.\n"),
    ],
)
def test_comments_and_prose_are_still_scanned(tool_use, run_hook, path, content):
    # Arrange
    payload = tool_use("Write", {"file_path": path, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)

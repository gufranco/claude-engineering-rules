from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "ai-process-leak-blocker"


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("/repo/src/wizard.ts", 'export const STEP_LABEL = "Phase 2";\n'),
        ("/repo/app/plans.py", 'TITLE = "Changes in the plan"\n'),
        (
            "/private/tmp/claude-501/project/session/scratchpad/notes.md",
            "Phase 2 of the plan\n",
        ),
    ],
)
def test_product_strings_and_scratch_notes_are_not_published_text(
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
        ("/repo/src/wizard.ts", "// Phase 2 wires the wizard\nexport const a = 1;\n"),
        ("/repo/app/plans.py", "x = 1  # per the plan\n"),
        ("/repo/README.md", "This lands in Phase 2.\n"),
    ],
)
def test_comments_and_prose_are_still_scanned(tool_use, run_hook, path, content):
    # Arrange
    payload = tool_use("Write", {"file_path": path, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: AI process language detected in artifact that other engineers will read.",
    )

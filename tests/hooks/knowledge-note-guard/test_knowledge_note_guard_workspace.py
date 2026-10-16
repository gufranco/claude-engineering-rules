from __future__ import annotations

import subprocess
from pathlib import Path

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _kng_support import HOOK, note

PROMPT_BODY = "# Continuation prompt\n\nNext steps for the session.\n"
WORKSPACE_EXCLUDE = "# local workspace, never committed\n/docs/\n"


def _git_init(vault: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet", str(vault)], check=True, capture_output=True
    )


def _register_workspace(vault: Path) -> None:
    exclude = vault / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text(WORKSPACE_EXCLUDE)


def test_a_file_in_the_registered_workspace_is_not_judged_as_a_note(
    tool_use, run_hook, vault, env
):
    # Arrange
    _git_init(vault)
    _register_workspace(vault)
    payload = tool_use(
        "Write", {"file_path": note(vault, "docs/PROMPT.md"), "content": PROMPT_BODY}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_docs_folder_the_vault_owns_is_still_judged(tool_use, run_hook, vault, env):
    # Arrange
    _git_init(vault)
    payload = tool_use(
        "Write", {"file_path": note(vault, "docs/PROMPT.md"), "content": PROMPT_BODY}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN001")


def test_a_vault_without_git_judges_the_workspace_name_as_a_note(
    tool_use, run_hook, vault, env
):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": note(vault, "docs/PROMPT.md"), "content": PROMPT_BODY}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN001")

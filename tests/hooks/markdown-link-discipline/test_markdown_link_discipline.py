"""Coverage for markdown-link-discipline hook.

Source rule: rules/markdown-links.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "markdown-link-discipline"
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_allows_non_markdown_file(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/tmp/foo.py", "content": "print('hi')"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_empty_command(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_markdown_with_linked_references(tool_use, assert_allows, tmp_path):
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text("# Doc\n\nSee [`README.md`](README.md) for details.\n")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "for details.",
            "new_string": "for details. Also [`CLAUDE.md`](CLAUDE.md).",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_advisory_specs_directory(tool_use, assert_allows):
    # Arrange
    target = REPO_ROOT / "specs" / "test-advisory.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("")
    try:
        payload = tool_use(
            "Write",
            {
                "file_path": str(target),
                "content": "Mention `README.md` without linking.\n",
            },
        )
        # Act / Assert
        assert_allows(HOOK, payload)
    finally:
        target.unlink(missing_ok=True)


def test_allows_bypass_env(tool_use, assert_allows, tmp_path):
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text("")
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "Mention `README.md` without linking.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"MARKDOWN_LINKS_DISABLE": "1"})


def test_allows_non_existing_path(tool_use, assert_allows, tmp_path):
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text("")
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "Hypothetical `foo/bar/baz.md` example.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_pre_existing_bare_reference(tool_use, assert_allows, tmp_path):
    """Editing a file that already contains a bare reference should not block
    when the edit does not introduce new bare references."""
    # Arrange
    target = tmp_path / "doc.md"
    target.write_text("Existing `README.md` reference.\n")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "Existing",
            "new_string": "Updated",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


SUBPROCESS_COV_DIR = REPO_ROOT / "tests" / "_subprocess_cov"
COVERAGERC_PATH = REPO_ROOT / ".coveragerc"


def _coverage_active() -> bool:
    if "COVERAGE_PROCESS_START" in os.environ or "COVERAGE_RUN" in os.environ:
        return True
    if "pytest_cov" in sys.modules or "pytest_cov.plugin" in sys.modules:
        return True
    cov_module = sys.modules.get("coverage")
    if cov_module is None:
        return False
    current = getattr(cov_module, "Coverage", None)
    if current is None:
        return False
    return getattr(current, "current", lambda: None)() is not None


def _build_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    if _coverage_active():
        env["COVERAGE_PROCESS_START"] = str(COVERAGERC_PATH)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{SUBPROCESS_COV_DIR}{os.pathsep}{existing_pp}"
            if existing_pp
            else str(SUBPROCESS_COV_DIR)
        )
    if extra:
        env.update(extra)
    return env


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = REPO_ROOT / "hooks" / "markdown-link-discipline.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        env=_build_subprocess_env(),
        timeout=6.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 0

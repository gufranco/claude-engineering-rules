from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed

HOOK = "markdown-link-discipline"
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_allows_non_markdown_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/tmp/foo.py", "content": "print('hi')"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_empty_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_markdown_with_linked_references(tool_use, run_hook, tmp_path):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_advisory_specs_directory(tool_use, run_hook, repo_scratch):
    # Arrange
    target = repo_scratch("specs/test-advisory.md", "")
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "Mention `README.md` without linking.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_bypass_env(tool_use, run_hook, tmp_path):
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

    # Act
    result = run_hook(HOOK, payload, env={"MARKDOWN_LINKS_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_allows_non_existing_path(tool_use, run_hook, tmp_path):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_pre_existing_bare_reference(tool_use, run_hook, tmp_path):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


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

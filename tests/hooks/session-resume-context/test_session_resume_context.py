from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parents[2]
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
from _helpers.cov_env import apply_coverage_env  # noqa: E402

EXCLUDE_MARKER = "# local workspace, never committed"

HOOK = "session-resume-context"


def session_payload(tool_use, cwd, source: str = "startup") -> dict:
    return tool_use(
        "",
        {},
        hook_event_name="SessionStart",
        session_id="test",
        source=source,
        cwd=str(cwd),
    )


def parse_context(stdout: str) -> str | None:
    if not stdout.strip():
        return None
    parsed = json.loads(stdout)
    return parsed.get("hookSpecificOutput", {}).get("additionalContext")


def write_checkpoints(cp_dir: Path, names: list[str]) -> None:
    cp_dir.mkdir()
    for name in names:
        (cp_dir / name).write_text(f"# {name}")


def test_surfaces_recent_checkpoint(run_hook, tool_use, tmp_path):
    # Arrange
    cp_dir = tmp_path / "checkpoints"
    cp_dir.mkdir()
    cp = cp_dir / "2026-05-29.md"
    cp.write_text("# Checkpoint\nLast worked on feature X.")
    os.utime(cp, (time.time(), time.time()))

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert code == 0
    ctx = parse_context(stdout)
    assert ctx is not None
    assert "Most recent checkpoint" in ctx
    assert "2026-05-29.md" in ctx
    assert "Last worked on feature X" in ctx


def test_surfaces_recent_spec_plan_when_no_checkpoints(run_hook, tool_use, tmp_path):
    # Arrange
    spec = tmp_path / "specs" / "2026-05-29-foo"
    spec.mkdir(parents=True)
    plan = spec / "plan.md"
    plan.write_text("# Plan\n\nBuilding feature Y.")

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert code == 0
    ctx = parse_context(stdout)
    assert ctx is not None
    assert "Most recent active plan" in ctx
    assert "plan.md" in ctx


def test_surfaces_session_log_as_last_resort(run_hook, tool_use, tmp_path):
    # Arrange
    sess = tmp_path / "sessions"
    sess.mkdir()
    log = sess / "2026-05-29.md"
    log.write_text("# Session\nContent.")

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert code == 0
    ctx = parse_context(stdout)
    assert ctx is not None
    assert "Most recent session log" in ctx


def test_checkpoint_takes_priority_over_spec(run_hook, tool_use, tmp_path):
    # Arrange
    cp_dir = tmp_path / "checkpoints"
    cp_dir.mkdir()
    (cp_dir / "2026-05-29.md").write_text("# CP")
    spec = tmp_path / "specs" / "2026-05-29-x"
    spec.mkdir(parents=True)
    (spec / "plan.md").write_text("# Plan")

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert code == 0
    ctx = parse_context(stdout)
    assert ctx is not None
    assert "Most recent checkpoint" in ctx


def test_lists_additional_checkpoints(run_hook, tool_use, tmp_path):
    # Arrange
    write_checkpoints(
        tmp_path / "checkpoints", ["2026-05-27.md", "2026-05-28.md", "2026-05-29.md"]
    )

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert code == 0
    ctx = parse_context(stdout)
    assert ctx is not None
    assert "Other recent checkpoints" in ctx


def test_includes_source_label(run_hook, tool_use, tmp_path):
    # Arrange
    spec = tmp_path / "specs" / "2026-05-29-x"
    spec.mkdir(parents=True)
    (spec / "plan.md").write_text("# Plan")

    # Act
    code, stdout, _ = run_hook(
        HOOK, session_payload(tool_use, tmp_path, source="compact")
    )

    # Assert
    assert code == 0
    ctx = parse_context(stdout)
    assert ctx is not None
    assert "SessionStart: compact" in ctx


def test_includes_preview_excerpt(run_hook, tool_use, tmp_path):
    # Arrange
    cp_dir = tmp_path / "checkpoints"
    cp_dir.mkdir()
    body = "\n".join(f"Line {i}" for i in range(50))
    (cp_dir / "2026-05-29.md").write_text(body)

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert code == 0
    ctx = parse_context(stdout)
    assert ctx is not None
    assert "Preview of" in ctx
    assert "Line 0" in ctx
    assert "more lines" in ctx


def test_emits_nothing_when_no_artifacts(run_hook, tool_use, tmp_path):
    # Arrange
    payload = session_payload(tool_use, tmp_path)

    # Act
    code, stdout, _ = run_hook(HOOK, payload)

    # Assert
    assert code == 0
    assert stdout.strip() == ""


def test_ignores_stale_artifacts(run_hook, tool_use, tmp_path):
    # Arrange
    cp_dir = tmp_path / "checkpoints"
    cp_dir.mkdir()
    cp = cp_dir / "2026-01-01.md"
    cp.write_text("# old")
    old = time.time() - (30 * 24 * 3600)
    os.utime(cp, (old, old))

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert code == 0
    assert stdout.strip() == ""


@pytest.mark.parametrize("event", ["PreToolUse", "PostToolUse", "Stop"])
def test_ignores_non_session_events(run_hook, tool_use, tmp_path, event):
    # Arrange
    cp_dir = tmp_path / "checkpoints"
    cp_dir.mkdir()
    (cp_dir / "2026-05-29.md").write_text("# CP")
    payload = tool_use("Read", {}, hook_event_name=event, cwd=str(tmp_path))

    # Act
    code, stdout, _ = run_hook(HOOK, payload)

    # Assert
    assert code == 0
    assert stdout.strip() == ""


GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def make_repo(root) -> None:
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "resume-hook@example.org"],
        ["config", "user.name", "Resume Hook"],
    ):
        subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            env={**os.environ, **GIT_ENV},
        )


def run_in_repo(run_hook, tool_use, repo, env=None):
    return run_hook(
        HOOK, session_payload(tool_use, repo), env={**GIT_ENV, **(env or {})}
    )


def test_surfaces_the_full_workspace_prompt_first(run_hook, tool_use, tmp_path):
    # Arrange
    make_repo(tmp_path)
    (tmp_path / "docs").mkdir()
    body = "\n".join(f"Prompt line {i}" for i in range(60))
    (tmp_path / "docs" / "PROMPT.md").write_text(body)
    (tmp_path / "checkpoints").mkdir()
    (tmp_path / "checkpoints" / "2026-09-29.md").write_text("# CP")

    # Act
    code, stdout, _ = run_in_repo(run_hook, tool_use, tmp_path)

    # Assert
    ctx = parse_context(stdout)
    assert code == 0
    assert ctx is not None
    assert "Continuation prompt" in ctx
    assert "Prompt line 59" in ctx
    assert "Recent checkpoints" in ctx


def test_surfaces_an_old_workspace_prompt(run_hook, tool_use, tmp_path):
    # Arrange
    make_repo(tmp_path)
    (tmp_path / "docs").mkdir()
    prompt = tmp_path / "docs" / "PROMPT.md"
    prompt.write_text("# Continue")
    old = time.time() - (90 * 24 * 3600)
    os.utime(prompt, (old, old))

    # Act
    code, stdout, _ = run_in_repo(run_hook, tool_use, tmp_path)

    # Assert
    ctx = parse_context(stdout)
    assert code == 0
    assert ctx is not None
    assert "Continuation prompt" in ctx


def test_names_the_workspace_in_a_repo_without_artifacts(run_hook, tool_use, tmp_path):
    # Arrange
    make_repo(tmp_path)

    # Act
    code, stdout, _ = run_in_repo(run_hook, tool_use, tmp_path)

    # Assert
    ctx = parse_context(stdout)
    assert code == 0
    assert ctx is not None
    assert ctx.startswith("WORKSPACE (SessionStart: startup)") is True
    assert f"`{tmp_path.resolve()}/docs/`" in ctx


def test_names_the_fallback_workspace_when_the_project_owns_docs(
    run_hook, tool_use, tmp_path
):
    # Arrange
    make_repo(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# Project docs")

    # Act
    code, stdout, _ = run_in_repo(run_hook, tool_use, tmp_path)

    # Assert
    ctx = parse_context(stdout)
    assert code == 0
    assert ctx is not None
    assert f"`{tmp_path.resolve()}/.work/`" in ctx


def test_surfaces_a_workspace_plan(run_hook, tool_use, tmp_path):
    # Arrange
    make_repo(tmp_path)
    exclude = tmp_path / ".git" / "info" / "exclude"
    exclude.write_text(f"{EXCLUDE_MARKER}\n/docs/\n")
    plan_dir = tmp_path / "docs" / "plans" / "2026-09-30-feature"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.md").write_text("# Plan\nWorkspace plan body.")

    # Act
    code, stdout, _ = run_in_repo(run_hook, tool_use, tmp_path)

    # Assert
    ctx = parse_context(stdout)
    assert code == 0
    assert ctx is not None
    assert "Most recent active plan" in ctx
    assert "Workspace plan body" in ctx


def test_skips_the_workspace_when_git_is_missing(run_hook, tool_use, tmp_path):
    # Arrange
    make_repo(tmp_path)

    # Act
    code, stdout, _ = run_in_repo(
        run_hook, tool_use, tmp_path, env={"PATH": str(tmp_path / "empty")}
    )

    # Assert
    assert code == 0
    assert stdout.strip() == ""


def test_disable_env_suppresses_output(run_hook, tool_use, tmp_path):
    # Arrange
    (tmp_path / "checkpoints").mkdir()
    (tmp_path / "checkpoints" / "2026-09-29.md").write_text("# CP")

    # Act
    code, stdout, _ = run_hook(
        HOOK,
        session_payload(tool_use, tmp_path),
        env={"SESSION_RESUME_CONTEXT_DISABLE": "1"},
    )

    # Assert
    assert (code, stdout) == (0, "")


def test_malformed_payload_is_ignored():
    # Arrange
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, "CLAUDE_BYPASS_STATE": os.devnull}),
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stdout) == (0, "")


def test_unreadable_checkpoint_is_listed_without_preview(run_hook, tool_use, tmp_path):
    # Arrange
    (tmp_path / "checkpoints" / "2026-09-30.md").mkdir(parents=True)

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    ctx = parse_context(stdout)
    assert code == 0
    assert ctx is not None
    assert "Most recent checkpoint" in ctx
    assert "Preview of" not in ctx


def test_broken_symlink_artifact_is_skipped(run_hook, tool_use, tmp_path):
    # Arrange
    (tmp_path / "checkpoints").mkdir()
    (tmp_path / "checkpoints" / "2026-09-30.md").symlink_to(tmp_path / "absent.md")

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert (code, stdout) == (0, "")

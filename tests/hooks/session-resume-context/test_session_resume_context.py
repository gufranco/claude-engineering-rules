"""Coverage for session-resume-context hook."""

from __future__ import annotations

import json
import os
import time

import pytest

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


# ---------------------------------------------------------------------------
# Surfacing recent artifacts
# ---------------------------------------------------------------------------


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
    assert ctx and "Most recent checkpoint" in ctx
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
    assert ctx and "Most recent active plan" in ctx
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
    assert ctx and "Most recent session log" in ctx


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
    assert ctx and "Most recent checkpoint" in ctx


def test_lists_additional_checkpoints(run_hook, tool_use, tmp_path):
    # Arrange
    cp_dir = tmp_path / "checkpoints"
    cp_dir.mkdir()
    for d in ["2026-05-27.md", "2026-05-28.md", "2026-05-29.md"]:
        (cp_dir / d).write_text(f"# {d}")

    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert code == 0
    ctx = parse_context(stdout)
    assert ctx and "Other recent checkpoints" in ctx


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
    assert ctx and "SessionStart: compact" in ctx


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
    assert ctx and "Preview of" in ctx
    assert "Line 0" in ctx
    assert "more lines" in ctx


# ---------------------------------------------------------------------------
# No artifacts
# ---------------------------------------------------------------------------


def test_emits_nothing_when_no_artifacts(run_hook, tool_use, tmp_path):
    # Act
    code, stdout, _ = run_hook(HOOK, session_payload(tool_use, tmp_path))

    # Assert
    assert code == 0
    assert not stdout.strip()


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
    assert not stdout.strip()


# ---------------------------------------------------------------------------
# Wrong event / malformed
# ---------------------------------------------------------------------------


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
    assert not stdout.strip()

from __future__ import annotations

import io
import os
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import (  # noqa: E402
    aaa_structure,
    analyzer_runs,
    bypass_writer,
    comment_regions,
    dangerous_command_push,
    hook_profile,
    outgoing_commits,
    suppression,
)
from _lib.aaa_structure import CaseLanguage  # noqa: E402
from _lib.mutation_cli import _catalog_codes  # noqa: E402
from _lib.mutation_detectors_methods import detect_map_upsert  # noqa: E402
from _lib.mutation_match_filter import is_inside_state_mgmt_scope  # noqa: E402
from _lib.output import warn  # noqa: E402

from _helpers.cov_env import apply_coverage_env  # noqa: E402


def _tokens(source: str) -> list[tokenize.TokenInfo]:
    return list(tokenize.generate_tokens(io.StringIO(source).readline))


def test_a_file_disable_after_the_scan_window_is_not_honoured():
    # Arrange
    lines = ["", *[f"x{i} = {i}" for i in range(12)], "# ruff: noqa"]

    # Act
    result = suppression.has_python_file_disable(lines)

    # Assert
    assert result is False


def test_an_unbalanced_push_segment_is_not_a_push():
    # Arrange
    segment = 'git push origin "main'

    # Act
    result = outgoing_commits._segment_push(segment, "", "/repo")

    # Assert
    assert result is None


def test_outgoing_messages_are_unknown_without_git(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("PATH", str(tmp_path))
    push = outgoing_commits.PushInvocation(str(tmp_path), ("HEAD",))

    # Act
    result = outgoing_commits.outgoing_messages(push)

    # Assert
    assert result is None


def test_a_map_call_without_a_map_receiver_is_not_flagged():
    # Arrange
    text = "cache.getOrInsert(key, value);\n"

    # Act
    result = detect_map_upsert(text, "typescript", "src/a.ts")

    # Assert
    assert result == []


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"CLAUDE_HOOK_PROFILE": "experimental"}, True),
        ({"CLAUDE_HOOK_PROFILE": "minimal", "CLAUDE_ENABLED_HOOKS": "tdd-gate"}, True),
    ],
)
def test_should_run_honours_unknown_profiles_and_enabled_hooks(
    monkeypatch, env, expected
):
    # Arrange
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    # Act
    result = hook_profile.should_run("tdd-gate")

    # Assert
    assert result is expected


def test_a_colon_inside_brackets_does_not_end_the_header():
    # Arrange
    source = "def test_x(a={1: 2}):\n    pass\n"
    tokens = _tokens(source)

    # Act
    result = aaa_structure._header_end(tokens, [t.start[0] for t in tokens], 1)

    # Assert
    assert result == 1


def test_a_header_without_a_colon_falls_back_to_the_def_line():
    # Arrange
    tokens = _tokens("x = (1)\n")

    # Act
    result = aaa_structure._header_end(tokens, [t.start[0] for t in tokens], 1)

    # Assert
    assert result == 1


def test_comments_that_are_not_markers_are_ignored():
    # Arrange
    text = "test('x', () => {\n  // setup the fixture\n  // Arrange\n});\n"

    # Act
    result = aaa_structure.markers_in(text, CaseLanguage.JAVASCRIPT)

    # Assert
    assert [marker.line for marker in result] == [2]


def test_the_audit_log_module_runs_as_a_program(tmp_path):
    # Arrange
    env = apply_coverage_env({**os.environ, "HOME": str(tmp_path)})
    env = {
        key: value for key, value in env.items() if key != "CLAUDE_HOOK_AUDIT_DISABLE"
    }
    script = REPO_ROOT / "hooks" / "_lib" / "audit_log.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(script), "--hook", "probe", "--decision", "allow"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # Assert
    assert proc.returncode == 0


def test_a_blank_hit_line_falls_back_to_the_filename_verdict():
    # Arrange
    lines = [""]

    # Act
    result = is_inside_state_mgmt_scope(lines, 0, "src/report.ts")

    # Assert
    assert result == (False, None)


def test_a_catalog_that_is_not_an_object_lists_no_codes():
    # Arrange
    data = ["IMM001"]

    # Act
    result = _catalog_codes(data)

    # Assert
    assert result == []


def test_a_warning_without_a_destination_or_next_step_has_only_its_purpose():
    # Arrange
    purpose = "records the edit"

    # Act
    result = warn(hook="probe", purpose=purpose)

    # Assert
    assert result == "INFO from probe\n\nPurpose:\n  records the edit\n"


def test_nested_parentheses_stay_inside_one_command_substitution():
    # Arrange
    text = "git push $(echo (a) b) origin"

    # Act
    result = dangerous_command_push.strip_command_substitutions(text)

    # Assert
    assert result == "git push X origin"


def test_a_block_scalar_indicator_without_a_body_masks_nothing():
    # Arrange
    text = "run: |\nnext: 1"

    # Act
    result = comment_regions._block_scalar_ranges(text)

    # Assert
    assert result == []


def test_clang_tidy_falls_back_to_a_known_install_when_not_on_path(
    monkeypatch, tmp_path
):
    # Arrange
    installed = tmp_path / "clang-tidy"
    installed.write_text("", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(analyzer_runs, "CLANG_TIDY_FALLBACKS", (str(installed),))

    # Act
    result = analyzer_runs.resolve_binary("clang-tidy")

    # Assert
    assert result == str(installed)


def test_a_failed_state_replace_removes_the_temporary_file(monkeypatch, tmp_path):
    # Arrange
    target = tmp_path / ".bypass-state.json"

    def refuse(source: str, destination: Path) -> None:
        raise OSError(f"cannot move {source} to {destination}")

    monkeypatch.setattr(bypass_writer.os, "replace", refuse)

    # Act
    attempt = lambda: bypass_writer._atomic_write(target, {"version": 1})  # noqa: E731

    # Assert
    with pytest.raises(OSError, match="cannot move"):
        attempt()
    assert list(tmp_path.iterdir()) == []


def test_map_upserts_on_a_declared_map_are_flagged_by_method():
    # Arrange
    text = (
        "const counts = new Map();\n"
        "counts.getOrInsert(key, 0);\n"
        "counts.getOrInsertComputed(key, () => 0);\n"
    )

    # Act
    result = detect_map_upsert(text, "typescript", "src/a.ts")

    # Assert
    assert [(match.line, match.col, match.detector) for match in result] == [
        (2, 1, "collection.map.get-or-insert"),
        (3, 1, "collection.map.get-or-insert-computed"),
    ]


def test_an_unclosed_command_substitution_hides_the_rest_of_the_line():
    # Arrange
    text = "echo $(date"

    # Act
    result = dangerous_command_push.strip_command_substitutions(text)

    # Assert
    assert result == "echo X"

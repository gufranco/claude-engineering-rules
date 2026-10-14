from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from _helpers.cov_env import apply_coverage_env

HOOK = Path(__file__).resolve().parents[3] / "hooks" / "mutation-method-blocker.py"
MUTATING_SOURCE = "export function add(items) {\n  items.push(1);\n  return items;\n}\n"
ISOLATION_VARS = (
    "MUTATION_METHOD_BATCH_MODE",
    "MUTATION_METHOD_LOCALE",
    "MUTATION_METHOD_CONCISE",
    "CLAUDE_DISABLED_HOOKS",
)


def _run(
    tmp_path: Path, args: tuple[str, ...], stdin: str, extra: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    inherited = {k: v for k, v in os.environ.items() if k not in ISOLATION_VARS}
    env = apply_coverage_env(
        {**inherited, "CLAUDE_BYPASS_STATE": str(tmp_path / "bypass.json"), **extra}
    )
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=30,
        check=False,
    )


def _write_payload(tmp_path: Path) -> str:
    return json.dumps(
        {
            "tool_name": "Write",
            "hook_event_name": "PreToolUse",
            "tool_input": {
                "file_path": str(tmp_path / "add.js"),
                "content": MUTATING_SOURCE,
            },
        }
    )


def test_batch_mode_reads_paths_from_stdin_skipping_blanks_and_comments(
    tmp_path: Path,
) -> None:
    # Arrange
    source = tmp_path / "add.js"
    source.write_text(MUTATING_SOURCE, encoding="utf-8")
    listing = f"# files to scan\n\n{source}\n"

    # Act
    proc = _run(tmp_path, (), listing, {"MUTATION_METHOD_BATCH_MODE": "1"})

    # Assert
    assert (proc.returncode, "[array.push]" in proc.stderr) == (2, True)


def test_regional_locale_falls_back_to_its_language_bundle(tmp_path: Path) -> None:
    # Arrange
    german = json.loads((HOOK.parent / "i18n" / "de.json").read_text(encoding="utf-8"))

    # Act
    proc = _run(
        tmp_path, (), _write_payload(tmp_path), {"MUTATION_METHOD_LOCALE": "de-AT"}
    )

    # Assert
    assert (proc.returncode, proc.stderr.splitlines()[0]) == (
        2,
        german["blocked_header"],
    )


def test_concise_mode_omits_the_reference_sections(tmp_path: Path) -> None:
    # Arrange
    extra = {"MUTATION_METHOD_CONCISE": "1"}

    # Act
    proc = _run(tmp_path, (), _write_payload(tmp_path), extra)

    # Assert
    assert (proc.returncode, "Fix references:" in proc.stderr) == (2, False)


def test_a_profile_disabled_hook_exits_zero_without_reading_input(
    tmp_path: Path,
) -> None:
    # Arrange
    extra = {"CLAUDE_DISABLED_HOOKS": "mutation-method-blocker"}

    # Act
    proc = _run(tmp_path, (), "{not json", extra)

    # Assert
    assert (proc.returncode, proc.stderr) == (0, "")


def test_version_flag_prints_the_version(tmp_path: Path) -> None:
    # Arrange
    args = ("--version",)

    # Act
    proc = _run(tmp_path, args, "", {})

    # Assert
    assert (proc.returncode, proc.stdout.startswith("mutation-method-blocker ")) == (
        0,
        True,
    )

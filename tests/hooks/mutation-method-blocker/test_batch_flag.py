from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[3] / "hooks" / "mutation-method-blocker.py"


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key != "MUTATION_METHOD_BATCH_MODE"
    }
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    env["CLAUDE_BYPASS_STATE"] = str(tmp_path / "bypass.json")
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=30,
        check=False,
    )


def test_batch_flag_blocks_a_mutating_file_passed_as_an_argument(
    tmp_path: Path,
) -> None:
    # Arrange
    source = tmp_path / "add.js"
    source.write_text(
        "export function add(items) {\n  items.push(1);\n  return items;\n}\n",
        encoding="utf-8",
    )

    # Act
    proc = _run(tmp_path, "--batch", str(source))

    # Assert
    assert (proc.returncode, "push" in proc.stderr) == (2, True)


def test_batch_flag_allows_a_clean_file_passed_as_an_argument(
    tmp_path: Path,
) -> None:
    # Arrange
    source = tmp_path / "add.js"
    source.write_text(
        "export const add = (items) => [...items, 1];\n", encoding="utf-8"
    )

    # Act
    proc = _run(tmp_path, "--batch", str(source))

    # Assert
    assert (proc.returncode, proc.stderr) == (0, "")

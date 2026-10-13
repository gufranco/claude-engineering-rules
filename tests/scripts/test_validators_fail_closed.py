from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / ".github" / "scripts"
UNREADABLE = b"# Title\n\xff\xfe not utf-8\n"
DECODE_ERROR = "'utf-8' codec can't decode byte 0xff in position 8: invalid start byte"


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=60,
        check=False,
    )


@pytest.mark.parametrize(
    "script", ["validate-clarity.py", "validate-normative-keywords.py"]
)
def test_an_unreadable_file_in_scope_fails_the_check(
    tmp_path: Path, script: str
) -> None:
    # Arrange
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "broken.md").write_bytes(UNREADABLE)

    # Act
    proc = _run(script, "--root", str(tmp_path))

    # Assert
    assert proc.returncode == 1
    assert proc.stdout.splitlines()[:2] == [
        "rules/broken.md: 1 finding(s)",
        f"     0  [unreadable]  cannot read: {DECODE_ERROR}",
    ]


def test_an_unreadable_markdown_file_fails_the_link_check(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "broken.md"
    target.write_bytes(UNREADABLE)

    # Act
    proc = _run("validate-markdown-links.py", str(target))

    # Assert
    assert proc.returncode == 1
    assert proc.stderr == f"FAILED: cannot read {target.resolve()}: {DECODE_ERROR}\n"


@pytest.mark.parametrize(
    "script",
    [
        "validate-clarity.py",
        "validate-normative-keywords.py",
        "audit-writing-quality.py",
    ],
)
def test_the_default_root_is_the_checkout_the_script_lives_in(script: str) -> None:
    # Arrange
    name = "validator_" + script.removesuffix(".py").replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module

    # Act
    spec.loader.exec_module(module)

    # Assert
    assert module.CLAUDE_ROOT == REPO_ROOT

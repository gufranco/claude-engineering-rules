from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "fix-markdown-links.py"
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.markdown_link_detector import BrokenLinkFinding, Finding  # noqa: E402


@pytest.fixture
def fixer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fix_markdown_links", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=30,
        check=False,
    )


def _commit(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "docs"], check=True, timeout=30
    )


def test_wrap_token_refuses_a_span_that_does_not_hold_the_token(fixer):
    # Arrange
    finding = Finding("a.md", 1, 1, "README.md", "README.md")

    # Act
    result = fixer._wrap_token("`OTHER.md` text", finding)

    # Assert
    assert result is None


def test_wrap_token_refuses_an_unclosed_span(fixer):
    # Arrange
    finding = Finding("a.md", 1, 1, "README.md", "README.md")

    # Act
    result = fixer._wrap_token("`README.md", finding)

    # Assert
    assert result is None


@pytest.mark.parametrize("line", ["[a](docs/x.md", "[a](docs/y.md)"])
def test_retarget_link_refuses_a_target_that_moved(fixer, line):
    # Arrange
    finding = BrokenLinkFinding("a.md", 1, 5, "a", "docs/x.md", "x.md")

    # Act
    result = fixer._retarget_link(line, finding)

    # Assert
    assert result is None


def test_retarget_link_keeps_the_fragment(fixer):
    # Arrange
    finding = BrokenLinkFinding("a.md", 1, 5, "a", "docs/x.md#part", "x.md")

    # Act
    result = fixer._retarget_link("[a](docs/x.md#part)", finding)

    # Assert
    assert result == "[a](x.md#part)"


def test_apply_line_edits_skips_findings_that_no_longer_match(fixer, tmp_path):
    # Arrange
    target = tmp_path / "a.md"
    target.write_text("`OTHER.md`\n", encoding="utf-8")
    finding = Finding("a.md", 1, 1, "README.md", "README.md")

    # Act
    applied = fixer.apply_fixes(target, [finding])

    # Assert
    assert (applied, target.read_text(encoding="utf-8")) == (0, "`OTHER.md`\n")


def test_every_tracked_file_is_fixed_when_none_is_named(scratch_repo_root):
    # Arrange
    (scratch_repo_root / "guide.md").write_text("See `README.md`.\n", encoding="utf-8")
    _commit(scratch_repo_root)

    # Act
    proc = _run(scratch_repo_root)

    # Assert
    assert proc.returncode == 0
    assert "wrapped 1 bare reference(s) in guide.md" in proc.stdout
    assert (scratch_repo_root / "guide.md").read_text(encoding="utf-8") == (
        "See [`README.md`](README.md).\n"
    )


def test_a_broken_target_is_retargeted_and_previewed(scratch_repo_root):
    # Arrange
    doc = scratch_repo_root / "docs" / "guide.md"
    doc.parent.mkdir()
    doc.write_text("Read [the readme](README.md).\n", encoding="utf-8")
    _commit(scratch_repo_root)

    # Act
    preview = _run(scratch_repo_root, str(doc), "--dry-run")
    applied = _run(scratch_repo_root, str(doc))

    # Assert
    assert "would rewrite 1 broken target(s) in docs/guide.md" in preview.stdout
    assert "rewrote 1 broken target(s) in docs/guide.md" in applied.stdout
    assert doc.read_text(encoding="utf-8") == "Read [the readme](../README.md).\n"


def test_unfixable_targets_are_listed_and_capped(scratch_repo_root):
    # Arrange
    links = "".join(f"[n{i}](missing-{i}.md)\n" for i in range(22))
    doc = scratch_repo_root / "many.md"
    doc.write_text(links, encoding="utf-8")

    # Act
    proc = _run(scratch_repo_root, str(doc))

    # Assert
    assert "WARNING: 22 broken link target(s)" in proc.stdout
    assert "  ... and 2 more" in proc.stdout


def test_an_unreadable_file_is_skipped(scratch_repo_root):
    # Arrange
    doc = scratch_repo_root / "binary.md"
    doc.write_bytes(b"\xff\xfe\x00")

    # Act
    proc = _run(scratch_repo_root, str(doc))

    # Assert
    assert proc.returncode == 0
    assert "Applied 0 fix(es) across 0 file(s)." in proc.stdout

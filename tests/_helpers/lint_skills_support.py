from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


from _helpers.cov_env import apply_coverage_env


LINTER = Path(__file__).resolve().parents[2] / "tools" / "lint-skills.py"


COMPLETE_FIELDS = 'argument-hint: "/example"\nallowed-tools: "Read"'


def run_linter(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINTER), *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=apply_coverage_env(dict(os.environ)),
        check=False,
    )


def make_skill(root: Path, name: str, frontmatter: str, body: str) -> Path:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    sk = skill_dir / "SKILL.md"
    sk.write_text(f"---\n{frontmatter}\n---\n{body}")
    return sk


__all__ = [
    "COMPLETE_FIELDS",
    "LINTER",
    "make_skill",
    "run_linter",
]

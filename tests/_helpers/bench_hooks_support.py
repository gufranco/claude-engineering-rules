from __future__ import annotations

import sys
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import bench_hooks  # noqa: E402


TABLE_HEADER = "hook  n  mean   p50    p95    p99    max    timeouts"
TABLE_RULE = "----  -  -----  -----  -----  -----  -----  --------"


def _write_hook(directory: Path, name: str, source: str) -> Path:
    path = directory / f"{name}.py"
    path.write_text(textwrap.dedent(source).lstrip() + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _allow_hook() -> str:
    return """
        import sys
        sys.exit(0)
    """


__all__ = [
    "REPO_ROOT",
    "SCRIPTS_DIR",
    "TABLE_HEADER",
    "TABLE_RULE",
    "_allow_hook",
    "_write_hook",
    "bench_hooks",
]

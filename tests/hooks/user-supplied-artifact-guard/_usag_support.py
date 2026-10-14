from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = ROOT / "hooks" / "user-supplied-artifact-guard.py"
sys.path.insert(0, str(ROOT / "hooks"))

HOOK_NAME = "user-supplied-artifact-guard"
CONTENT_SHA256 = "ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73"
BYPASS_TTL_S = 120
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _stage(repo: Path, name: str, payload: bytes) -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    subprocess.run(["git", "add", "--", name], check=True, cwd=str(repo), timeout=30)


def _stdin_with(payload: object, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))


class VanishingPath(Path):
    def is_file(self) -> bool:
        return True

    def stat(self, *_args: object, **_kwargs: object) -> object:
        raise OSError("file vanished between checks")

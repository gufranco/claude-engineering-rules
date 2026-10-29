from __future__ import annotations

import json
import os
import shlex
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from faker import Faker

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "frontend-render-gate.py"
SIPS_STUB = Path(__file__).resolve().parent / "sips_stub.py"
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
from _helpers.cov_env import apply_coverage_env  # noqa: E402

GH = "g" + "h"
fake = Faker()
Faker.seed(5521)
SHARP = (2880, 4200)


def png(path: Path, size: tuple[int, int]) -> Path:
    header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" + struct.pack(">II", *size)
    path.write_bytes(header)
    return path


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout


def repo_with_branch(
    root: Path, base_files: dict[str, str], branch_files: dict[str, str | None]
) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", f"{fake.user_name()}@repo.test")
    git(repo, "config", "user.name", fake.name())
    git(repo, "config", "commit.gpgsign", "false")
    for name, content in {"README.md": "base\n", **base_files}.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "feature")
    for name, content in branch_files.items():
        target = repo / name
        if content is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "change")
    return repo


def failing_git(stub_dir: Path, subcommand: str) -> str:
    real = shutil.which("git")
    stub_dir.mkdir(parents=True, exist_ok=True)
    stub = stub_dir / "git"
    stub.write_text(
        "#!/bin/sh\n"
        f'case " $* " in *" {subcommand} "*) exit 1 ;; esac\n'
        f'exec "{real}" "$@"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def run_gate(
    tool_input: dict[str, object],
    cwd: Path,
    tool_name: str = "Bash",
    path: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        **{k: v for k, v in os.environ.items() if k != "FRONTEND_RENDER_GATE_DISABLE"},
        "CLAUDE_BYPASS_STATE": os.devnull,
        "CLAUDE_HOOK_AUDIT_DISABLE": "1",
        "CHANGE_MARKER_SIPS": shlex.join([sys.executable, str(SIPS_STUB)]),
        **({"PATH": path} if path is not None else {}),
        **(extra_env or {}),
    }
    payload = json.dumps(
        {"tool_name": tool_name, "tool_input": tool_input, "cwd": str(cwd)}
    )
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=apply_coverage_env(env),
        timeout=60,
        check=False,
    )


def decision(result: subprocess.CompletedProcess[str]) -> str:
    if not result.stdout.strip():
        return ""
    parsed = json.loads(result.stdout)
    return str(parsed["hookSpecificOutput"]["permissionDecision"])

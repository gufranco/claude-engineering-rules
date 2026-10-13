from __future__ import annotations

import os
import subprocess

import pytest


from _ai_review_request_support import FAKE_GH, load_hook, login


@pytest.fixture
def hook():
    return load_hook()


@pytest.fixture
def fake_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    me = login()
    repo = tmp_path / "repo"
    repo.mkdir()
    git_env = {**os.environ, "HOME": str(tmp_path)}
    for cmd in (
        ["git", "init", "-q", "-b", "feature"],
        ["git", "remote", "add", "origin", "git@github.com:acme/app.git"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, env=git_env, timeout=30)
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "FAKE_GH_LOG": str(tmp_path / "gh.log"),
        "FAKE_GH_ME": me,
    }
    return {"env": env, "repo": repo, "log": tmp_path / "gh.log", "me": me}

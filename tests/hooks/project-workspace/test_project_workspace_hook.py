"""Coverage for the project-workspace hook.

SessionStart claims a local workspace folder through the git exclude file,
Stop blocks once when the continuation prompt is older than the newest change,
and PreToolUse on Bash refuses a forced add that would stage the workspace.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parents[2]
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
from _helpers.cov_env import apply_coverage_env  # noqa: E402

HOOK = "project-workspace"
RNG = random.Random(20260930)
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


@pytest.fixture(autouse=True)
def isolated_git_config(monkeypatch):
    for key, value in GIT_ENV.items():
        monkeypatch.setenv(key, value)


def words(count: int = 4) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    return " ".join(
        "".join(RNG.choice(alphabet) for _ in range(RNG.randint(3, 9)))
        for _ in range(count)
    )


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def make_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    run_git(root, "init", "-q", "-b", "main")
    run_git(root, "config", "user.email", f"{words(1)}@example.org")
    run_git(root, "config", "user.name", words(2))
    run_git(root, "config", "commit.gpgsign", "false")
    return root


def commit_file(repo: Path, rel: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(words())
    run_git(repo, "add", "-f", "--", rel)
    run_git(repo, "commit", "-q", "--no-verify", "-m", "add file")


def exclude_text(repo: Path) -> str:
    return (repo / ".git" / "info" / "exclude").read_text()


def start(run_hook, repo: Path, env: dict[str, str] | None = None):
    payload = {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(repo)}
    return run_hook(HOOK, payload, env={**GIT_ENV, **(env or {})})


def stop(run_hook, repo: Path, active: bool = False):
    payload = {"hook_event_name": "Stop", "stop_hook_active": active, "cwd": str(repo)}
    return run_hook(HOOK, payload, env=GIT_ENV)


def bash(run_hook, tool_use, repo: Path, command: str, env=None):
    payload = tool_use("Bash", {"command": command}, cwd=str(repo))
    return run_hook(HOOK, payload, env={**GIT_ENV, **(env or {})})


def claim_docs_with_stale_prompt(run_hook, repo: Path) -> None:
    start(run_hook, repo)
    (repo / "docs").mkdir()
    prompt = repo / "docs" / "PROMPT.md"
    prompt.write_text(words())
    stamp = time.time() - 600
    os.utime(prompt, (stamp, stamp))
    (repo / "main.py").write_text(words())


def test_start_claims_docs_in_the_exclude_file(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")

    code, stdout, _ = start(run_hook, repo)

    assert (code, stdout) == (0, "")
    assert "\n/docs/\n" in exclude_text(repo)


def test_start_claims_work_when_the_project_tracks_docs(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")

    code, _, _ = start(run_hook, repo)

    assert code == 0
    assert "\n/.work/\n" in exclude_text(repo)
    assert "/docs/" not in exclude_text(repo)


def test_start_never_touches_project_files(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")
    commit_file(repo, ".gitignore")
    before = run_git(repo, "status", "--porcelain", "--untracked-files=all")

    start(run_hook, repo)

    after = run_git(repo, "status", "--porcelain", "--untracked-files=all")
    assert (before, after) == ("", "")


def test_start_releases_a_folder_the_project_began_tracking(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)
    commit_file(repo, "docs/guide.md")

    start(run_hook, repo)

    assert "/docs/" not in exclude_text(repo)
    assert "\n/.work/\n" in exclude_text(repo)


def test_start_is_silent_outside_a_repository(run_hook, tmp_path):
    code, stdout, stderr = start(run_hook, tmp_path)

    assert (code, stdout, stderr) == (0, "", "")


def test_start_writes_nothing_when_git_is_missing(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")
    before = exclude_text(repo)

    code, stdout, stderr = start(run_hook, repo, env={"PATH": str(tmp_path)})

    assert (code, stdout) == (0, "")
    assert "project-workspace" in stderr
    assert exclude_text(repo) == before


def test_stop_blocks_when_the_prompt_is_stale(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")
    claim_docs_with_stale_prompt(run_hook, repo)

    code, stdout, _ = stop(run_hook, repo)

    decision = json.loads(stdout)
    assert code == 0
    assert decision["decision"] == "block"
    assert "docs/PROMPT.md" in decision["reason"]


def test_stop_allows_the_second_stop_in_a_chain(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")
    claim_docs_with_stale_prompt(run_hook, repo)

    code, stdout, _ = stop(run_hook, repo, active=True)

    assert (code, stdout) == (0, "")


def test_stop_allows_a_clean_tree(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")

    code, stdout, _ = stop(run_hook, repo)

    assert (code, stdout) == (0, "")


def test_stop_allows_outside_a_repository(run_hook, tmp_path):
    code, stdout, _ = stop(run_hook, tmp_path)

    assert (code, stdout) == (0, "")


def test_stop_names_the_fallback_folder(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")
    (repo / "main.py").write_text(words())

    code, stdout, _ = stop(run_hook, repo)

    assert code == 0
    assert ".work/PROMPT.md" in json.loads(stdout)["reason"]


def test_stop_allows_and_logs_when_no_folder_is_free(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")
    for name in ("docs", ".work", ".work-local"):
        commit_file(repo, f"{name}/owned.md")
    (repo / "main.py").write_text(words())

    code, stdout, stderr = stop(run_hook, repo)

    assert (code, stdout) == (0, "")
    assert "no free workspace" in stderr


@pytest.mark.parametrize(
    "command",
    [
        "git add -f docs/PROMPT.md",
        "git add --force docs",
        "git add -fA",
        "git add -f .",
        "git -C . add -f -- docs/research.md",
        "npm test && git add -f 'docs/*.md'",
        "git stage --force docs/plans",
        "GIT_TRACE=0 git add -f docs",
        "git add -f :/",
    ],
)
def test_stage_blocks_a_forced_add_of_the_workspace(
    run_hook, tool_use, tmp_path, command
):
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)

    code, _, stderr = bash(run_hook, tool_use, repo, command)

    assert code == 2
    assert "docs/" in stderr


@pytest.mark.parametrize(
    "command",
    [
        "git add docs/PROMPT.md",
        "git add -f src/main.py",
        "git add -A",
        "git status",
        "echo git add -f docs",
        "FOO=1",
        "git -C",
        "echo 'unterminated",
        "",
    ],
)
def test_stage_allows_other_commands(run_hook, tool_use, tmp_path, command):
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)

    code, _, _ = bash(run_hook, tool_use, repo, command)

    assert code == 0


def test_stage_blocks_a_forced_add_from_inside_the_workspace(
    run_hook, tool_use, tmp_path
):
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)
    (repo / "docs").mkdir()

    code, _, _ = bash(run_hook, tool_use, repo / "docs", "git add -f PROMPT.md")

    assert code == 2


def test_stage_blocks_a_forced_add_when_git_fails(run_hook, tool_use, tmp_path):
    repo = make_repo(tmp_path / "project")

    code, _, stderr = bash(
        run_hook, tool_use, repo, "git add -f docs", env={"PATH": str(tmp_path)}
    )

    assert code == 2
    assert "could not" in stderr


def test_stage_blocks_an_unparseable_forced_add(run_hook, tool_use, tmp_path):
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)

    code, _, _ = bash(run_hook, tool_use, repo, "git add -f 'docs/PROMPT.md")

    assert code == 2


def test_stage_allows_outside_a_repository(run_hook, tool_use, tmp_path):
    code, _, _ = bash(run_hook, tool_use, tmp_path, "git add -f docs")

    assert code == 0


def test_env_bypass_skips_every_event(run_hook, tool_use, tmp_path):
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)

    code, _, _ = bash(
        run_hook,
        tool_use,
        repo,
        "git add -f docs",
        env={"PROJECT_WORKSPACE_DISABLE": "1"},
    )

    assert code == 0


@pytest.mark.parametrize("raw", ["not json", "[]"])
def test_malformed_payload_is_ignored(raw):
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"

    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=raw,
        capture_output=True,
        text=True,
        env=apply_coverage_env(
            {**os.environ, "CLAUDE_BYPASS_STATE": os.devnull, **GIT_ENV}
        ),
        check=False,
    )

    assert (proc.returncode, proc.stdout) == (0, "")


def test_non_dict_tool_input_is_ignored(run_hook, tmp_path):
    repo = make_repo(tmp_path / "project")
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": "git add -f docs",
        "cwd": str(repo),
    }

    code, _, _ = run_hook(HOOK, payload, env=GIT_ENV)

    assert code == 0


def test_non_bash_tool_is_ignored(run_hook, tool_use, tmp_path):
    repo = make_repo(tmp_path / "project")
    payload = tool_use(
        "Write", {"file_path": str(repo / "docs" / "x.md")}, cwd=str(repo)
    )

    code, stdout, _ = run_hook(HOOK, payload, env=GIT_ENV)

    assert (code, stdout) == (0, "")

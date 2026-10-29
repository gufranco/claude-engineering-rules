from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = REPO_ROOT / "tests"
HOOKS_DIR = REPO_ROOT / "hooks"
FIXTURES_DIR = TESTS_DIR / "fixtures"
CASES_FILE = FIXTURES_DIR / "hook-smoke-cases.json"
PLACEHOLDER = "@WORK_DIR@"
DEFAULT_CWD = "cwd"
CASE_TIMEOUT_SECONDS = 60
STAGED_SECRET = "AKIA" + "Q" * 16
PLACEHOLDER_IDENTITY = {
    "GIT_AUTHOR_NAME": "Placeholder",
    "GIT_AUTHOR_EMAIL": "placeholder@example.com",
    "GIT_COMMITTER_NAME": "Placeholder",
    "GIT_COMMITTER_EMAIL": "placeholder@example.com",
}
RESOLVED_GITCONFIG = "[user]\n    name = Resolved\n    email = resolved@valid.test\n"
ISOLATION_DEFAULTS = {
    "CLAUDE_HOOK_AUDIT_DISABLE": "1",
    "CLAUDE_BYPASS_STATE": os.devnull,
}


@dataclass(frozen=True, slots=True)
class Case:
    section: str
    description: str
    hook: str
    fixture: str
    expect: int
    render: bool = False
    cwd: str = DEFAULT_CWD
    env: dict[str, str] = field(default_factory=dict)


def load_cases(path: Path) -> list[Case]:
    return [Case(**entry) for entry in json.loads(path.read_text(encoding="utf-8"))]


def git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        check=True,
        capture_output=True,
        timeout=CASE_TIMEOUT_SECONDS,
    )


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git("init", "-q", cwd=path)
    return path


def prepare(work: Path) -> None:
    init_repo(work / DEFAULT_CWD)
    secret = init_repo(work / "staged-secret")
    (secret / "settings.ini").write_text(
        f"aws_key = {STAGED_SECRET}\n", encoding="utf-8"
    )
    git("add", "settings.ini", cwd=secret)
    override = init_repo(work / "local-override")
    git("config", "--local", "user.email", "override@example.com", cwd=override)
    git("config", "--local", "user.name", "Override", cwd=override)
    placeholder = init_repo(work / "placeholder-commit")
    git(
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "placeholder commit",
        cwd=placeholder,
        env=PLACEHOLDER_IDENTITY,
    )
    init_repo(work / "no-identity")
    init_repo(work / "resolved")
    resolved_home = work / "resolved-home"
    resolved_home.mkdir()
    (resolved_home / ".gitconfig").write_text(RESOLVED_GITCONFIG, encoding="utf-8")


def case_input(case: Case, work: Path) -> bytes:
    raw = (FIXTURES_DIR / case.fixture).read_bytes()
    return raw.replace(PLACEHOLDER.encode(), str(work).encode()) if case.render else raw


def case_env(case: Case, work: Path) -> dict[str, str]:
    overrides = {
        key: value.replace(PLACEHOLDER, str(work)) for key, value in case.env.items()
    }
    return {**ISOLATION_DEFAULTS, **os.environ, **overrides}


def run_case(case: Case, work: Path) -> int:
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / case.hook)],
        input=case_input(case, work),
        cwd=work / case.cwd,
        env=case_env(case, work),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=CASE_TIMEOUT_SECONDS,
        check=False,
    ).returncode


def verdict(case: Case, actual: int) -> str:
    if actual == case.expect:
        return f"  PASS: {case.description} (exit {actual})"
    return f"  FAIL: {case.description} (expected exit {case.expect}, got {actual})"


def run_suite(cases: list[Case], work: Path) -> int:
    failed = 0
    section = None
    for case in cases:
        if case.section != section:
            section = case.section
            print(f"\n=== {section} ===")
        actual = run_case(case, work)
        failed += actual != case.expect
        print(verdict(case, actual))
    print(f"\n=== Results ===\n  Passed: {len(cases) - failed}\n  Failed: {failed}\n")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run every hook against its smoke fixtures."
    )
    parser.add_argument("--cases", type=Path, default=CASES_FILE)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="hook-smoke-") as tmp:
        work = Path(tmp)
        prepare(work)
        return run_suite(load_cases(args.cases), work)


if __name__ == "__main__":
    sys.exit(main())

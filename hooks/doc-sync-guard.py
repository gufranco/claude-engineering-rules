#!/usr/bin/env python3
"""Block a commit whose staged diff makes existing documentation false.

Documentation that describes code is a claim about the code. This hook runs
at `git commit`, reads the staged diff, and refuses the commit when the
change falsifies a claim that is still on disk.

Only four checks ship, each chosen because it leaves no judgment call:

  1. The code reads an environment variable `.env.example` does not name.
     The example file is a complete list by definition, so the absence is
     certain rather than a style opinion.
  2. An exported symbol disappears while tracked markdown still names it.
  3. A parser flag disappears while tracked markdown still names it.
  4. A `package.json` script disappears while tracked markdown still names it.

Checks 2 through 4 are one mechanism: a name vanished from the code while a
document still asserts it exists.

Documenting an addition is the author's obligation and is deliberately not
enforced here. A README that documents three of five flags is a style choice
no tool can distinguish from an omission, and a check that needs a maybe is a
check that trains people to disable the hook.

Historical records are exempt. A changelog, an architecture decision record,
an incident report, and an archived plan are supposed to name things that no
longer exist.

Staging the affected document clears the check. The hook verifies the
document was touched, never that it was touched correctly, because
correctness is a review judgment.

Enforces: rules/doc-truth.md
Bypass: DOC_SYNC_DISABLE=1 in the parent shell.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


try:
    from _lib.hook_profile import should_run  # type: ignore
except ImportError:  # pragma: no cover

    def should_run(_id: str) -> bool:
        return True


from _lib.bypass import is_bypassed  # noqa: E402

GIT_TIMEOUT_SECONDS = 10

COMMIT_COMMAND = re.compile(r"(?:^|&&|\|\||;|\|)\s*git\s+(?:-[^\s]+\s+)*commit\b")

HELP_FLAG = re.compile(r"\s--help\b")

ENV_READ_PATTERNS = (
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]{2,})"),
    re.compile(r"process\.env\[['\"]([A-Z][A-Z0-9_]{2,})['\"]\]"),
    re.compile(r"os\.environ\[['\"]([A-Z][A-Z0-9_]{2,})['\"]\]"),
    re.compile(r"os\.environ\.get\(['\"]([A-Z][A-Z0-9_]{2,})['\"]"),
    re.compile(r"os\.getenv\(['\"]([A-Z][A-Z0-9_]{2,})['\"]"),
    re.compile(r"env!\(['\"]([A-Z][A-Z0-9_]{2,})['\"]\)"),
    re.compile(r"ENV\[['\"]([A-Z][A-Z0-9_]{2,})['\"]\]"),
)

EXPORT_PATTERNS = (
    re.compile(r"export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"export\s+(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"export\s+(?:type|interface|enum)\s+([A-Za-z_$][\w$]*)"),
)

FLAG_PATTERNS = (
    re.compile(r"add_argument\(\s*['\"](--[a-z][a-z0-9-]*)['\"]"),
    re.compile(r"\.option\(\s*['\"](--[a-z][a-z0-9-]*)['\"]"),
    re.compile(r"\.long\(\s*['\"]([a-z][a-z0-9-]*)['\"]\s*\)"),
)

SCRIPT_KEY = re.compile(r'^\s*"([a-z][a-z0-9:_-]*)"\s*:\s*"')

ENV_EXAMPLE_NAMES = (".env.example", ".env.sample", ".env.template")

HISTORICAL_MARKERS = (
    "changelog",
    "/docs/adr/",
    "/specs/",
    "/archive/",
    "/history/",
    "release-notes",
    "releasenotes",
)

DOC_SUFFIXES = (".md", ".mdx", ".rst")


def _git(cwd: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _staged_paths(cwd: Path) -> set[str]:
    out = _git(cwd, "diff", "--cached", "--name-only")
    if out is None:
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def _staged_diff(cwd: Path) -> str:
    return _git(cwd, "diff", "--cached", "-U0") or ""


def _added_lines(diff: str) -> list[str]:
    return [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _removed_lines(diff: str) -> list[str]:
    return [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]


def _matches(patterns: tuple[re.Pattern[str], ...], lines: list[str]) -> set[str]:
    found: set[str] = set()
    for line in lines:
        for pattern in patterns:
            found.update(pattern.findall(line))
    return found


def _is_historical(path: str) -> bool:
    lowered = f"/{path.lower()}"
    return any(marker in lowered for marker in HISTORICAL_MARKERS)


def _tracked_docs(cwd: Path) -> list[str]:
    out = _git(cwd, "ls-files")
    if out is None:
        return []
    return [
        line.strip()
        for line in out.splitlines()
        if line.strip().lower().endswith(DOC_SUFFIXES)
        and not _is_historical(line.strip())
    ]


def _env_example_names(cwd: Path, tracked: set[str]) -> tuple[str | None, set[str]]:
    for candidate in ENV_EXAMPLE_NAMES:
        if candidate not in tracked:
            continue
        try:
            text = (cwd / candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None, set()
        names = set()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            names.add(stripped.split("=", 1)[0].strip().lstrip("export ").strip())
        return candidate, names
    return None, set()


def _docs_naming(cwd: Path, docs: list[str], needle: str) -> list[str]:
    hits: list[str] = []
    for doc in docs:
        try:
            text = (cwd / doc).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(rf"(?<![\w-]){re.escape(needle)}(?![\w-])", text):
            hits.append(doc)
    return hits


def _script_names(cwd: Path, ref: str) -> set[str] | None:
    out = _git(cwd, "show", f"{ref}:package.json")
    if out is None:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return set()
    return {str(key) for key in scripts}


def _collect_findings(cwd: Path) -> list[str]:
    tracked_all = _git(cwd, "ls-files")
    if tracked_all is None:
        return []
    tracked = {line.strip() for line in tracked_all.splitlines() if line.strip()}

    staged = _staged_paths(cwd)
    if not staged:
        return []

    diff = _staged_diff(cwd)
    if not diff:
        return []

    added = _added_lines(diff)
    removed = _removed_lines(diff)
    docs = _tracked_docs(cwd)
    findings: list[str] = []

    example_path, documented_env = _env_example_names(cwd, tracked)
    if example_path is not None and example_path not in staged:
        introduced = _matches(ENV_READ_PATTERNS, added) - _matches(
            ENV_READ_PATTERNS, removed
        )
        for name in sorted(introduced - documented_env):
            findings.append(
                f"environment variable {name} is read by the staged code but "
                f"{example_path} does not name it and is not staged"
            )

    unstaged_docs = [doc for doc in docs if doc not in staged]

    dropped_exports = _matches(EXPORT_PATTERNS, removed) - _matches(
        EXPORT_PATTERNS, added
    )
    for name in sorted(dropped_exports):
        for doc in _docs_naming(cwd, unstaged_docs, name):
            findings.append(f"export {name} was removed but {doc} still names it")

    dropped_flags = _matches(FLAG_PATTERNS, removed) - _matches(FLAG_PATTERNS, added)
    for flag in sorted(dropped_flags):
        needle = flag if flag.startswith("--") else f"--{flag}"
        for doc in _docs_naming(cwd, unstaged_docs, needle):
            findings.append(f"flag {needle} was removed but {doc} still names it")

    if "package.json" in staged:
        before = _script_names(cwd, "HEAD")
        after = _script_names(cwd, ":0")
        if before is not None and after is not None:
            for script in sorted(before - after):
                for doc in _docs_naming(cwd, unstaged_docs, script):
                    findings.append(
                        f"package script {script} was removed but {doc} still names it"
                    )

    return findings


def main() -> int:
    if os.environ.get("DOC_SYNC_DISABLE") == "1":
        return 0
    if is_bypassed("doc-sync-guard"):
        return 0
    if not should_run("doc-sync-guard"):
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        return 0

    if data.get("tool_name", "Bash") != "Bash":
        return 0

    tool_input = data.get("tool_input", data.get("input", {})) or {}
    command = tool_input.get("command", "")
    if not command or HELP_FLAG.search(command):
        return 0
    if not COMMIT_COMMAND.search(command):
        return 0

    cwd = Path(data.get("cwd") or os.getcwd())
    if not cwd.is_dir():
        return 0

    findings = _collect_findings(cwd)
    if not findings:
        return 0

    detail = "\n".join(f"  - {item}" for item in findings)
    sys.stderr.write(
        "BLOCKED: this commit makes existing documentation false.\n"
        f"{detail}\n"
        "Documentation that describes code is a claim about the code. Stage "
        "the corrected document alongside the change.\n"
        "Historical records (changelogs, ADRs, specs) are exempt and were "
        "already skipped.\n"
        "Rule: rules/doc-truth.md\n"
        "Bypass for a genuine false positive: export DOC_SYNC_DISABLE=1\n"
    )
    _audit(
        hook="doc-sync-guard",
        decision="block",
        tool="Bash",
        reason="staged change falsifies existing documentation",
        command_excerpt=command[:240],
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

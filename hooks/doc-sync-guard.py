#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

from _lib.audit_log import record as _audit  # noqa: E402


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.commit_scope import commits_all, repo_dir  # noqa: E402
from _lib.git_invocation import strip_git_global_options  # noqa: E402

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

EXPORT_ANCHORS = ("export",)

FLAG_ANCHORS = ("add_argument(", ".option(", ".long(")

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


def _staged_paths(cwd: Path, base: str) -> set[str]:
    out = _git(cwd, "diff", base, "--name-only")
    if out is None:
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def _staged_diff(cwd: Path, base: str) -> str:
    return _git(cwd, "diff", base, "-U0") or ""


def _code_hunks(diff: str) -> str:
    kept: list[str] = []
    in_doc = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_doc = line.rsplit(" b/", 1)[-1].lower().endswith(DOC_SUFFIXES)
        if not in_doc:
            kept.append(line)
    return "\n".join(kept)


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
            names.add(stripped.split("=", 1)[0].strip().removeprefix("export ").strip())
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


def _diff_sections(diff: str) -> list[list[str]]:
    lines = diff.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("diff --git ")]
    return [lines[a:b] for a, b in zip(starts, [*starts[1:], len(lines)])]


def _deleted_file_removals(diff: str) -> list[tuple[str, list[str]]]:
    return [
        (
            section[0].rsplit(" b/", 1)[-1],
            [
                line[1:]
                for line in section
                if line.startswith("-") and not line.startswith("---")
            ],
        )
        for section in _diff_sections(diff)
        if any(line.startswith("deleted file mode") for line in section[1:4])
    ]


def _deletion_only_names(
    code_diff: str, patterns: tuple[re.Pattern[str], ...], removed: list[str]
) -> dict[str, frozenset[str]]:
    deleted = _deleted_file_removals(code_diff)
    deleted_lines = {line for _, lines in deleted for line in lines}
    elsewhere = _matches(
        patterns, [line for line in removed if line not in deleted_lines]
    )
    stems: dict[str, frozenset[str]] = {}
    for path, lines in deleted:
        for name in _matches(patterns, lines) - elsewhere:
            stems = {**stems, name: stems.get(name, frozenset()) | {Path(path).stem}}
    return stems


def _docs_naming_with_context(
    cwd: Path, docs: list[str], needle: str, context: frozenset[str]
) -> list[str]:
    hits = _docs_naming(cwd, docs, needle)
    if not context:
        return hits
    return [
        doc
        for doc in hits
        if any(
            stem in (cwd / doc).read_text(encoding="utf-8", errors="replace")
            for stem in context
        )
    ]


def _surviving_definitions(
    cwd: Path,
    base: str,
    patterns: tuple[re.Pattern[str], ...],
    anchors: tuple[str, ...],
) -> set[str]:
    scope = ("--cached",) if base == "--cached" else ()
    expressions = [arg for anchor in anchors for arg in ("-e", anchor)]
    excluded = [f":(exclude)*{suffix}" for suffix in DOC_SUFFIXES]
    out = _git(
        cwd, "grep", *scope, "-h", "-I", "-F", *expressions, "--", ".", *excluded
    )
    if out is None:
        return set()
    return _matches(patterns, out.splitlines())


def _env_findings(
    cwd: Path, tracked: set[str], staged: set[str], added: list[str], removed: list[str]
) -> list[str]:
    example_path, documented_env = _env_example_names(cwd, tracked)
    if example_path is None or example_path in staged:
        return []
    introduced = _matches(ENV_READ_PATTERNS, added) - _matches(
        ENV_READ_PATTERNS, removed
    )
    return [
        f"environment variable {name} is read by the staged code but "
        f"{example_path} does not name it and is not staged"
        for name in sorted(introduced - documented_env)
    ]


def _export_findings(
    cwd: Path, base: str, code_diff: str, unstaged_docs: list[str]
) -> list[str]:
    removed = _removed_lines(code_diff)
    dropped_exports = _matches(EXPORT_PATTERNS, removed) - _surviving_definitions(
        cwd, base, EXPORT_PATTERNS, EXPORT_ANCHORS
    )
    context = _deletion_only_names(code_diff, EXPORT_PATTERNS, removed)
    return [
        f"export {name} was removed but {doc} still names it"
        for name in sorted(dropped_exports)
        for doc in _docs_naming_with_context(
            cwd, unstaged_docs, name, context.get(name, frozenset())
        )
    ]


def _flag_findings(
    cwd: Path, base: str, code_diff: str, unstaged_docs: list[str]
) -> list[str]:
    removed = _removed_lines(code_diff)
    dropped_flags = _matches(FLAG_PATTERNS, removed) - _surviving_definitions(
        cwd, base, FLAG_PATTERNS, FLAG_ANCHORS
    )
    context = _deletion_only_names(code_diff, FLAG_PATTERNS, removed)
    return [
        f"flag {_flag_needle(flag)} was removed but {doc} still names it"
        for flag in sorted(dropped_flags)
        for doc in _docs_naming_with_context(
            cwd, unstaged_docs, _flag_needle(flag), context.get(flag, frozenset())
        )
    ]


def _flag_needle(flag: str) -> str:
    return flag if flag.startswith("--") else f"--{flag}"


def _script_findings(
    cwd: Path, staged: set[str], unstaged_docs: list[str]
) -> list[str]:
    if "package.json" not in staged:
        return []
    before = _script_names(cwd, "HEAD")
    after = _script_names(cwd, ":0")
    if before is None or after is None:
        return []
    return [
        f"package script {script} was removed but {doc} still names it"
        for script in sorted(before - after)
        for doc in _docs_naming(cwd, unstaged_docs, script)
    ]


def _collect_findings(cwd: Path, base: str = "--cached") -> list[str]:
    tracked_all = _git(cwd, "ls-files")
    if tracked_all is None:
        return []
    tracked = {line.strip() for line in tracked_all.splitlines() if line.strip()}

    staged = _staged_paths(cwd, base)
    if not staged:
        return []

    diff = _staged_diff(cwd, base)
    if not diff:
        return []

    code_diff = _code_hunks(diff)
    added = _added_lines(code_diff)
    removed = _removed_lines(code_diff)
    docs = _tracked_docs(cwd)
    env_findings = _env_findings(cwd, tracked, staged, added, removed)
    unstaged_docs = [doc for doc in docs if doc not in staged]
    return [
        *env_findings,
        *_export_findings(cwd, base, code_diff, unstaged_docs),
        *_flag_findings(cwd, base, code_diff, unstaged_docs),
        *_script_findings(cwd, staged, unstaged_docs),
    ]


def _skip() -> bool:
    return (
        os.environ.get("DOC_SYNC_DISABLE") == "1"
        or is_bypassed("doc-sync-guard")
        or not should_run("doc-sync-guard")
    )


def _commit_command(data: dict) -> str:
    if data.get("tool_name", "Bash") != "Bash":
        return ""
    tool_input = data.get("tool_input", data.get("input", {})) or {}
    command = tool_input.get("command", "")
    if not command or HELP_FLAG.search(command):
        return ""
    if not COMMIT_COMMAND.search(strip_git_global_options(command)):
        return ""
    return command


def _block(command: str, findings: list[str]) -> int:
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


def main() -> int:
    if _skip():
        return 0

    data = read_hook_payload("doc-sync-guard")
    command = _commit_command(data)
    if not command:
        return 0

    cwd = Path(repo_dir(command, str(data.get("cwd") or os.getcwd())))
    if not cwd.is_dir():
        return 0

    findings = _collect_findings(cwd, "HEAD" if commits_all(command) else "--cached")
    if not findings:
        return 0
    return _block(command, findings)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Scan staged files for secrets before git commit.

Intercepts Bash tool calls that run git commit. Scans all staged files
for 40+ secret patterns. Blocks the commit if any secrets are found.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b")

SKIP_EXTENSIONS = {
    ".lock",
    ".lockb",
    ".sum",
    ".mod",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".pdf",
    ".doc",
    ".docx",
}
SKIP_FILES = {
    ".env.example",
    ".env.template",
    ".env.sample",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "bun.lockb",
    "Cargo.lock",
    "go.sum",
    "Gemfile.lock",
    "poetry.lock",
    "composer.lock",
}
SKIP_PATHS = {"node_modules/", "vendor/", ".git/", "dist/", "build/"}

SECRET_PATTERNS = [
    ("AWS Access Key", r"AKIA[0-9A-Z]{16}"),
    ("AWS Secret Key", r"(?i)aws_secret_access_key\s*[=:]\s*[A-Za-z0-9/+=]{40}"),
    ("Anthropic Admin Key", r"sk-ant-admin-[a-zA-Z0-9_-]{20,}"),
    ("Anthropic API Key", r"sk-ant-[a-zA-Z0-9_-]{20,}"),
    ("OpenAI API Key", r"sk-[a-zA-Z0-9]{20,}"),
    ("Google API Key", r"AIza[0-9A-Za-z_-]{35}"),
    ("Stripe Live Key", r"sk_live_[0-9a-zA-Z]{24,}"),
    ("Stripe Publishable", r"pk_live_[0-9a-zA-Z]{24,}"),
    ("Stripe Restricted Key", r"rk_(?:live|test)_[0-9a-zA-Z]{24,}"),
    ("GitHub Token", r"gh[pousr]_[A-Za-z0-9_]{36,}"),
    ("GitHub Fine-Grained", r"github_pat_[A-Za-z0-9_]{22,}"),
    ("GitLab Token", r"glpat-[A-Za-z0-9_-]{20,}"),
    ("Slack Token", r"xox[baprs]-[0-9a-zA-Z-]{10,}"),
    (
        "Slack Webhook",
        r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+",
    ),
    ("Discord Webhook", r"https://discord(?:app)?\.com/api/webhooks/\d+/[\w-]+"),
    ("Telegram Bot Token", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    ("Vercel Token", r"vercel_[A-Za-z0-9_-]{24,}"),
    ("Vercel OAuth Token", r"\bv1\.[A-Za-z0-9]{40,}\b"),
    ("Supabase Key", r"sbp_[a-f0-9]{40}"),
    ("Hugging Face Token", r"hf_[A-Za-z0-9]{34,}"),
    ("Replicate Token", r"r8_[A-Za-z0-9]{20,}"),
    ("Groq API Key", r"gsk_[A-Za-z0-9]{20,}"),
    ("npm Token", r"npm_[A-Za-z0-9]{36}"),
    ("PyPI Token", r"pypi-[A-Za-z0-9_-]{16,}"),
    ("Databricks Token", r"dapi[a-f0-9]{32}"),
    ("SendGrid Key", r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}"),
    ("Twilio Key", r"SK[a-f0-9]{32}"),
    ("Mailgun Key", r"key-[a-zA-Z0-9]{32}"),
    (
        "Heroku API Key",
        r"(?i)heroku.*[=:]\s*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    ),
    ("Private Key Header", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ("JWT Token", r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+"),
    ("Generic Password", r"(?i)(?:password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{8,}['\"]"),
    (
        "Generic Secret",
        r"(?i)(?:secret|token|api_key|apikey)\s*[=:]\s*['\"][^'\"]{8,}['\"]",
    ),
    ("Database URL", r"(?:postgres|mysql|mongodb|redis)://[^\s'\"]+:[^\s'\"]+@"),
    ("Connection String", r"(?i)(?:server|data source)=[^;]+;.*(?:password|pwd)=[^;]+"),
    (
        "Bearer Token",
        r"(?i)(?:authorization|bearer)\s*[:=]\s*bearer\s+[A-Za-z0-9_\-\.]+",
    ),
    ("API Key Header", r"(?i)x-api-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    ("Basic Auth", r"(?i)authorization\s*[:=]\s*basic\s+[A-Za-z0-9+/=]{10,}"),
]

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.cli_invocations import invocations  # noqa: E402
from _lib.git_invocation import strip_git_global_options  # noqa: E402


def should_skip(filepath):
    """Check if a file should be skipped."""
    if any(filepath.startswith(p) or f"/{p}" in filepath for p in SKIP_PATHS):
        return True
    basename = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath
    if basename in SKIP_FILES:
        return True
    ext = ""
    if "." in basename:
        ext = "." + basename.rsplit(".", 1)[-1]
    if ext.lower() in SKIP_EXTENSIONS:
        return True
    return False


LEADING_CD = re.compile(r"""\s*cd\s+(?:'([^']*)'|"([^"]*)"|(\S+))\s*(?:&&|;)""")
GIT_DASH_C = re.compile(r"""\bgit\s+-C\s+(?:'([^']*)'|"([^"]*)"|(\S+))""")
COMMIT_ALL = re.compile(r"\bcommit\b[^\n;&|]*\s(?:--all|-[a-zA-Z]*a[a-zA-Z]*)(?=\s|$)")
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
MAX_UNTRACKED_BYTES = 512 * 1024
MAX_UNTRACKED_FILES = 2000


class ScanError(Exception):
    pass


def _first_group(match: re.Match[str]) -> str:
    return next(group for group in match.groups() if group is not None)


def _repo_dir(command: str, cwd: str) -> str:
    base = cwd or os.getcwd()
    for pattern in (LEADING_CD, GIT_DASH_C):
        match = (
            pattern.match(command) if pattern is LEADING_CD else pattern.search(command)
        )
        if match:
            target = os.path.expandvars(os.path.expanduser(_first_group(match)))
            base = os.path.join(base, target)
    return base


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", repo, *args], capture_output=True, text=True, timeout=10
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        raise ScanError(f"git {' '.join(args)} failed: {error}") from error


def _is_repository(repo: str) -> bool:
    try:
        return _git(repo, "rev-parse", "--git-dir").returncode == 0
    except ScanError:
        return False


def _diff(repo: str, *args: str) -> str:
    result = _git(repo, "diff", "--no-color", "--no-ext-diff", *args)
    if result.returncode != 0:
        raise ScanError(f"git diff {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _added_lines(diff_text: str) -> list[tuple[str, int, str]]:
    added: list[tuple[str, int, str]] = []
    path, number = "", 0
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
            continue
        header = HUNK_HEADER.match(line)
        if header:
            number = int(header.group(1))
            continue
        if line.startswith("+"):
            added = [*added, (path, number, line[1:])]
            number += 1
        elif not line.startswith("-"):
            number += 1
    return added


def _add_scope(command: str) -> tuple[bool, list[str]]:
    whole = False
    paths: list[str] = []
    for call in invocations(command, "git"):
        args = list(call.args)
        while args[:1] in (["-C"], ["-c"]) and len(args) > 1:
            args = args[2:]
        if args[:1] != ["add"]:
            continue
        rest = args[1:]
        whole = whole or any(a in ("-A", "--all", ".", ":/") for a in rest)
        paths = [*paths, *(a for a in rest if not a.startswith("-") and a != ".")]
    return whole, paths


def _within(name: str, paths: list[str]) -> bool:
    cleaned = [p.removeprefix("./").rstrip("/") for p in paths]
    return any(name == p or name.startswith(f"{p}/") for p in cleaned)


def _untracked_lines(repo: str, paths: list[str] | None) -> list[tuple[str, int, str]]:
    listing = _git(repo, "ls-files", "--others", "--exclude-standard")
    if listing.returncode != 0:
        raise ScanError(f"git ls-files failed: {listing.stderr.strip()}")
    names = listing.stdout.splitlines()[:MAX_UNTRACKED_FILES]
    lines: list[tuple[str, int, str]] = []
    for name in (n for n in names if paths is None or _within(n, paths)):
        target = os.path.join(repo, name)
        if os.path.getsize(target) > MAX_UNTRACKED_BYTES:
            continue
        with open(target, encoding="utf-8", errors="replace") as handle:
            lines = [*lines, *((name, n, text) for n, text in enumerate(handle, 1))]
    return lines


def _candidate_lines(command: str, repo: str) -> list[tuple[str, int, str]]:
    whole, paths = _add_scope(command)
    lines = _added_lines(_diff(repo, "--cached"))
    if COMMIT_ALL.search(command) or whole:
        lines = [*lines, *_added_lines(_diff(repo))]
    elif paths:
        lines = [*lines, *_added_lines(_diff(repo, "--", *paths))]
    if whole or paths:
        lines = [*lines, *_untracked_lines(repo, None if whole else paths)]
    return lines


def scan_command(command: str, cwd: str) -> list[tuple[str, int, str]]:
    repo = _repo_dir(command, cwd)
    if not _is_repository(repo):
        return []
    findings: list[tuple[str, int, str]] = []
    for path, number, text in _candidate_lines(command, repo):
        if not path or should_skip(path):
            continue
        name = next((n for n, p in SECRET_PATTERNS if re.search(p, text)), None)
        if name is not None and (path, number, name) not in findings:
            findings = [*findings, (path, number, name)]
    return findings


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main():
    if os.environ.get("SECRET_SCANNER_DISABLE") == "1":
        return 0
    if is_bypassed("secret-scanner"):
        return 0
    if not should_run("secret-scanner"):
        sys.exit(0)
    data = read_hook_payload("secret-scanner")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command or not COMMIT_PATTERN.search(strip_git_global_options(command)):
        sys.exit(0)

    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else ""
    try:
        findings = scan_command(command, cwd)
    except (ScanError, OSError) as error:
        print(
            "BLOCKED: secret-scanner could not read what this commit would record, "
            f"so it was not checked: {error}",
            file=sys.stderr,
        )
        _audit(
            hook="secret-scanner",
            decision="block",
            tool="Bash",
            reason="scan failed",
            command_excerpt=None,
        )
        sys.exit(2)
    if not findings:
        sys.exit(0)

    report = ["BLOCKED: Potential secrets detected in what this commit would record.\n"]
    report = [
        *report,
        *(f"  {path}:{number}: {name}" for path, number, name in findings),
    ]
    report.append("\nThe matched text is not shown, so it stays out of the session.")
    report.append("Remove the secrets and try again.")
    report.append("If these are false positives, commit manually outside Claude Code.")
    print("\n".join(report), file=sys.stderr)
    _audit(
        hook="secret-scanner",
        decision="block",
        tool="Bash",
        reason="secret found in staged files",
        command_excerpt=None,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()

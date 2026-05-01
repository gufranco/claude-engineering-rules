#!/usr/bin/env python3
"""Block git operations that would use the wrong author identity.

Identity resolution itself is delegated to the user's private
`~/.gitconfig` via `includeIf "hasconfig:remote.*.url:..."`. This hook
does not know any real email. It only verifies consistency:

- Commit creation (`git commit`, `--amend`, `cherry-pick`, `rebase`,
  `revert`, `merge` with custom message): effective `user.email` is
  non-empty, no `[user]` block exists in the repository's `.git/config`,
  and no inline `GIT_AUTHOR_EMAIL=` or `GIT_COMMITTER_EMAIL=` is set on
  the same command line.

- Push (`git push`, `--force`, `--force-with-lease`): walks
  `git log --format=%ae @{push}..HEAD` (capped at 200 commits) and
  blocks if any author email is empty or matches a placeholder pattern
  like `*@example.com`, `*@example.org`, `*@example.net`, or
  `noreply.example.*`.

- Config mutation (`git config user.email <value>`, `git config
  user.name <value>`, `git config --local user.*`): blocks any local
  write to `user.*`. Allows `--global` writes; those edit
  `~/.gitconfig`, the source of truth.

Read-only commands (`git config --get`, `git status`, `git log`) are
not gated.

Bypass: GIT_AUTHOR_GUARD_DISABLE=1 in the hook's environment.

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

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover
    def _audit(**_fields):  # type: ignore
        return None

# Bounded log walk on push.
PUSH_LOG_LIMIT = 200

# Placeholder author emails. Real identities never match these.
PLACEHOLDER_EMAIL = re.compile(
    r"@example\.(?:com|org|net)$|^noreply\.example\.|^placeholder@",
    re.IGNORECASE,
)

# Commit-creation triggers. `merge` is included because a non-fast-forward
# merge produces a commit with the local user as author.
COMMIT_TRIGGERS = re.compile(
    r"\bgit\s+(?:commit|cherry-pick|rebase|revert|merge)\b"
)

# Push triggers. `--force-with-lease` and `--force` are inside `push`.
PUSH_TRIGGER = re.compile(r"\bgit\s+push\b")

# `git config` writes to user.*: capture for analysis.
CONFIG_USER_WRITE = re.compile(
    r"\bgit\s+config\b(?P<rest>[^|;&]*)"
)

# Read-only `git config` flags.
CONFIG_READ_FLAGS = re.compile(r"--(?:get|get-all|get-regexp|list|show-origin|show-scope)\b")

# Identity-overriding env injections on the same command line.
ENV_AUTHOR_OVERRIDE = re.compile(
    r"\b(?:GIT_AUTHOR_EMAIL|GIT_COMMITTER_EMAIL|GIT_AUTHOR_NAME|GIT_COMMITTER_NAME)=\S+"
)

# `cd <dir> && ...` prefix capture.
CD_PREFIX = re.compile(r"^\s*cd\s+(?P<dir>\S+)\s*&&\s*")

# `git -C <dir>` flag capture.
GIT_C_FLAG = re.compile(r"\bgit\s+-C\s+(?P<dir>\S+)")


def repo_dir(command: str) -> Path:
    """Best-effort resolution of the working directory the command targets."""
    cd_match = CD_PREFIX.search(command)
    if cd_match:
        candidate = Path(os.path.expanduser(cd_match.group("dir")))
        if candidate.is_dir():
            return candidate
    git_c = GIT_C_FLAG.search(command)
    if git_c:
        candidate = Path(os.path.expanduser(git_c.group("dir")))
        if candidate.is_dir():
            return candidate
    return Path.cwd()


def run_git(cwd: Path, *args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 1, ""
    return result.returncode, result.stdout.strip()


def has_local_user_block(cwd: Path) -> bool:
    """True if .git/config contains a [user] block with name or email."""
    code, top = run_git(cwd, "rev-parse", "--show-toplevel")
    if code != 0 or not top:
        return False
    config_path = Path(top) / ".git" / "config"
    if not config_path.is_file():
        return False
    try:
        content = config_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    in_user = False
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("["):
            in_user = line.lower().startswith("[user]") or line.lower().startswith('[user "')
            continue
        if in_user and ("=" in line):
            key = line.split("=", 1)[0].strip().lower()
            if key in {"email", "name"}:
                return True
    return False


def is_inside_repo(cwd: Path) -> bool:
    code, out = run_git(cwd, "rev-parse", "--is-inside-work-tree")
    return code == 0 and out == "true"


def block(message: str) -> None:
    sys.stderr.write(message + "\n")
    _audit(hook="git-author-guard", decision="block", tool="Bash",
           reason=message.split("\n", 1)[0][:120])
    sys.exit(2)


def check_commit(command: str, cwd: Path) -> None:
    if ENV_AUTHOR_OVERRIDE.search(command):
        block(
            "BLOCKED: identity override env var on the command line "
            "(GIT_AUTHOR_EMAIL/GIT_COMMITTER_EMAIL/NAME).\n"
            "Identity must come from ~/.gitconfig includeIf resolution.\n"
            "See: standards/git-identity.md\n"
            f"Command: {command}"
        )

    if not is_inside_repo(cwd):
        return

    if has_local_user_block(cwd):
        block(
            "BLOCKED: repository .git/config contains a local [user] block "
            "that overrides ~/.gitconfig resolution.\n"
            "Remove it: `git config --local --unset user.email && "
            "git config --local --unset user.name`\n"
            "Identity must come from ~/.gitconfig includeIf rules.\n"
            "See: standards/git-identity.md"
        )

    code, email = run_git(cwd, "config", "--get", "user.email")
    if code != 0 or not email:
        block(
            "BLOCKED: `user.email` is not set for this repository.\n"
            "Configure ~/.gitconfig with includeIf rules matching the "
            "repository's remote URL.\n"
            "See: standards/git-identity.md"
        )

    if PLACEHOLDER_EMAIL.search(email):
        block(
            f"BLOCKED: resolved user.email is a placeholder ({email}).\n"
            "Update ~/.gitconfig with the real identity for this remote.\n"
            "See: standards/git-identity.md"
        )


def check_push(command: str, cwd: Path) -> None:
    if not is_inside_repo(cwd):
        return

    code, log = run_git(
        cwd,
        "log",
        f"--max-count={PUSH_LOG_LIMIT}",
        "--format=%ae",
        "@{push}..HEAD",
    )
    if code != 0:
        # No upstream set, or detached HEAD. Fall back to validating HEAD.
        code, head_email = run_git(cwd, "log", "-1", "--format=%ae", "HEAD")
        if code != 0:
            return
        emails = [head_email] if head_email else []
    else:
        emails = [line.strip() for line in log.splitlines() if line.strip()]

    for email in emails:
        if not email:
            block(
                "BLOCKED: a commit in @{push}..HEAD has an empty author "
                "email.\n"
                "Rewrite the affected commit with the correct identity "
                "before pushing.\n"
                "See: standards/git-identity.md"
            )
        if PLACEHOLDER_EMAIL.search(email):
            block(
                f"BLOCKED: a commit in @{{push}}..HEAD has a placeholder "
                f"author email ({email}).\n"
                "Rewrite the affected commit with the real identity "
                "before pushing.\n"
                "See: standards/git-identity.md"
            )


def check_config_mutation(command: str) -> None:
    match = CONFIG_USER_WRITE.search(command)
    if not match:
        return
    rest = match.group("rest")
    if CONFIG_READ_FLAGS.search(rest):
        return
    # Only care about user.* writes.
    if not re.search(r"\buser\.(?:email|name)\b", rest):
        return
    has_global = re.search(r"--global\b", rest) is not None
    has_local = re.search(r"--local\b", rest) is not None
    has_system = re.search(r"--system\b", rest) is not None
    has_file = re.search(r"--file[\s=]\S+", rest) is not None

    if has_global or has_system or has_file:
        return

    if has_local:
        reason = "explicit --local write to user.*"
    else:
        reason = "unscoped write to user.* defaults to --local"

    block(
        f"BLOCKED: {reason}.\n"
        "Identity must come from ~/.gitconfig (use --global or edit "
        "the file directly).\n"
        "See: standards/git-identity.md\n"
        f"Command: {match.group(0).strip()}"
    )


def main() -> None:
    if os.environ.get("GIT_AUTHOR_GUARD_DISABLE") == "1":
        sys.stderr.write(
            "git-author-guard: bypass active (GIT_AUTHOR_GUARD_DISABLE=1)\n"
        )
        _audit(hook="git-author-guard", decision="bypass",
               bypass_env="GIT_AUTHOR_GUARD_DISABLE")
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not isinstance(command, str) or not command:
        sys.exit(0)

    cwd = repo_dir(command)

    check_config_mutation(command)

    if PUSH_TRIGGER.search(command):
        check_push(command, cwd)
        sys.exit(0)

    if COMMIT_TRIGGERS.search(command):
        check_commit(command, cwd)
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()

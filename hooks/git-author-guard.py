#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.git_invocation import strip_git_global_options  # noqa: E402
from _lib.shell_segments import mask_literal_text  # noqa: E402

from _lib.audit_log import record as _audit  # noqa: E402


PUSH_LOG_LIMIT = 200

PLACEHOLDER_EMAIL = re.compile(
    r"@example\.(?:com|org|net)$|^noreply\.example\.|^placeholder@",
    re.IGNORECASE,
)

HOST_DERIVED_EMAIL = re.compile(
    r"\.(?:local|lan|localdomain|home|internal)$|@localhost$|\(none\)",
    re.IGNORECASE,
)

UNSIGNED_STATES = frozenset({"N", "B"})

COMMIT_TRIGGERS = re.compile(
    r"\bgit\b(?:\s+-(?:c\s+\S+|C\s+\S+|[a-zA-Z]+(?:=\S+)?))*\s+"
    r"(?:commit|cherry-pick|rebase|revert|merge)\b"
)

PUSH_TRIGGER = re.compile(
    r"\bgit\b(?:\s+-(?:c\s+\S+|C\s+\S+|[a-zA-Z]+(?:=\S+)?))*\s+push\b"
)

CONFIG_USER_WRITE = re.compile(r"\bgit\s+config\b(?P<rest>[^|;&]*)")

CONFIG_READ_FLAGS = re.compile(
    r"--(?:get|get-all|get-regexp|list|show-origin|show-scope)\b"
)

CONFIG_REMOVE_FLAGS = re.compile(r"--(?:unset|unset-all|remove-section)\b")

USER_KEY_WITH_VALUE = re.compile(r"\buser\.(?:email|name)\s+\S")

AUTHOR_FLAG = re.compile(r"(?:^|\s)--author(?:=|\s)")

ENV_AUTHOR_OVERRIDE = re.compile(
    r"\b(?:GIT_AUTHOR_EMAIL|GIT_COMMITTER_EMAIL|GIT_AUTHOR_NAME|GIT_COMMITTER_NAME)=\S+"
)

INLINE_C_OVERRIDE = re.compile(
    r"-c\s+(?:user\.(?:email|name)|commit\.gpgsign|tag\.gpgsign|gpg\.\w+)\s*=\s*\S+",
    re.IGNORECASE,
)

CD_PREFIX = re.compile(r"^\s*cd\s+(?P<dir>\S+)\s*&&\s*")

GIT_C_FLAG = re.compile(r"\bgit\s+-C\s+(?P<dir>\S+)")


def repo_dir(command: str) -> Path:
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
    code, top = run_git(cwd, "rev-parse", "--show-toplevel")
    if code != 0:
        return False
    config_path = Path(top) / ".git" / "config"
    if not config_path.is_file():
        return False
    content = config_path.read_text(encoding="utf-8", errors="replace")
    in_user = False
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("["):
            in_user = line.lower().startswith("[user]") or line.lower().startswith(
                '[user "'
            )
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
    _audit(
        hook="git-author-guard",
        decision="block",
        tool="Bash",
        reason=message.split("\n", 1)[0][:120],
    )
    sys.exit(2)


def _check_command_overrides(command: str) -> None:
    if ENV_AUTHOR_OVERRIDE.search(command):
        block(
            "BLOCKED: identity override env var on the command line "
            "(GIT_AUTHOR_EMAIL/GIT_COMMITTER_EMAIL/NAME).\n"
            "Identity must come from ~/.gitconfig includeIf resolution.\n"
            "See: standards/git-identity.md\n"
            f"Command: {command}"
        )

    if AUTHOR_FLAG.search(command):
        block(
            "BLOCKED: --author override on the commit command line.\n"
            "Identity must come from ~/.gitconfig includeIf resolution.\n"
            "See: standards/git-identity.md\n"
            f"Command: {command}"
        )

    if INLINE_C_OVERRIDE.search(command):
        block(
            "BLOCKED: inline `-c user.email=`/`-c user.name=`/"
            "`-c commit.gpgsign=`/`-c tag.gpgsign=` override on the "
            "command line.\n"
            "Identity and signing must come from ~/.gitconfig "
            "includeIf resolution. Never override per-command.\n"
            "See: standards/git-identity.md\n"
            f"Command: {command}"
        )


def _check_resolved_identity(cwd: Path) -> None:
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


def check_commit(command: str, cwd: Path) -> None:
    _check_command_overrides(command)
    if not is_inside_repo(cwd):
        return
    _check_resolved_identity(cwd)


def _unpushed_identity_log(cwd: Path) -> str | None:
    fields = "--format=<%ae>%x09<%ce>%x09%G?%x09%h"
    code, log = run_git(
        cwd, "log", f"--max-count={PUSH_LOG_LIMIT}", fields, "@{push}..HEAD"
    )
    if code == 0:
        return log
    code, log = run_git(cwd, "log", "-1", fields, "HEAD")
    return log if code == 0 else None


def _parse_identity_line(line: str) -> tuple[str, str, str, str]:
    author, committer, signature, short = line.split("\t")
    return author[1:-1], committer[1:-1], signature, short


def _check_host_derived(email: str, role: str, short: str) -> None:
    if not HOST_DERIVED_EMAIL.search(email):
        return
    block(
        f"BLOCKED: commit {short} has a {role} email derived from the "
        f"machine name ({email}).\n"
        "Git guessed it because it could not read ~/.gitconfig, which "
        "happens when a script runs git without HOME.\n"
        "Rewrite the commit with the configured identity before pushing, "
        "and make the script pass os.environ through.\n"
        "See: standards/git-identity.md"
    )


def _check_committer(committer: str, expected: str, short: str) -> None:
    if not expected or committer == expected:
        return
    block(
        f"BLOCKED: commit {short} was committed as {committer}, but this "
        f"repository resolves user.email to {expected}.\n"
        "Rewrite the commit with the configured identity before pushing.\n"
        "See: standards/git-identity.md"
    )


def _check_signature(signature: str, signing: bool, short: str) -> None:
    if not signing or signature not in UNSIGNED_STATES:
        return
    block(
        f"BLOCKED: commit {short} carries no valid signature, but "
        "commit.gpgsign is true for this repository.\n"
        "A commit made by a script without HOME is never signed. "
        "Re-create it with signing before pushing.\n"
        "See: standards/git-identity.md"
    )


def _push_expectations(cwd: Path) -> tuple[str, bool]:
    code, email = run_git(cwd, "config", "--get", "user.email")
    expected = email if code == 0 else ""
    code, signing = run_git(cwd, "config", "--bool", "--get", "commit.gpgsign")
    return expected, code == 0 and signing == "true"


def _check_push_email(email: str) -> None:
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


def check_push(command: str, cwd: Path) -> None:
    if not is_inside_repo(cwd):
        return
    log = _unpushed_identity_log(cwd)
    if log is None:
        return
    expected, signing = _push_expectations(cwd)
    for line in log.splitlines():
        author, committer, signature, short = _parse_identity_line(line)
        _check_push_email(author)
        _check_host_derived(author, "author", short)
        _check_host_derived(committer, "committer", short)
        _check_committer(committer, expected, short)
        _check_signature(signature, signing, short)


def check_config_mutation(command: str) -> None:
    match = CONFIG_USER_WRITE.search(command)
    if not match:
        return
    rest = match.group("rest")
    if CONFIG_READ_FLAGS.search(rest) or CONFIG_REMOVE_FLAGS.search(rest):
        return
    if not USER_KEY_WITH_VALUE.search(rest):
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


from _lib.hook_profile import should_run  # noqa: E402


def _should_skip() -> bool:
    if not should_run("git-author-guard"):
        return True
    if is_bypassed("git-author-guard"):
        return True
    if os.environ.get("GIT_AUTHOR_GUARD_DISABLE") != "1":
        return False
    sys.stderr.write("git-author-guard: bypass active (GIT_AUTHOR_GUARD_DISABLE=1)\n")
    _audit(
        hook="git-author-guard",
        decision="bypass",
        bypass_env="GIT_AUTHOR_GUARD_DISABLE",
    )
    return True


def main() -> None:
    if _should_skip():
        sys.exit(0)

    data = read_hook_payload("git-author-guard")

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not isinstance(command, str) or not command:
        sys.exit(0)

    cwd = repo_dir(command)
    executed = mask_literal_text(command)
    matched = strip_git_global_options(executed)

    check_config_mutation(matched)

    if PUSH_TRIGGER.search(matched):
        check_push(executed, cwd)
        sys.exit(0)

    if COMMIT_TRIGGERS.search(matched):
        check_commit(executed, cwd)
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()

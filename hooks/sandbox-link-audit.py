#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.audit_log import record as _audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.hook_warning import emit_user_notice  # noqa: E402
from _lib.machine_identity import probe  # noqa: E402
from _lib.sandbox_links import is_temporary  # noqa: E402

HOOK = "sandbox-link-audit"
BYPASS_ENV = "SANDBOX_LINK_DISABLE"
SKIPPED_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".tox"}
)
MAX_DEPTH = 40
MAX_DIR_ENTRIES = 5000
MAX_REPORTED = 20
CONFIG_LEVELS = 1
REASON = (
    "These links point into a temp dir that is deleted when the session ends, so "
    "each one will dangle in a real tree:\n{rows}\n"
    "Restore each real file or link from its source, such as rerunning the real "
    "install step, then remove the temp link. A clean git status does not show "
    "this, since the files can be ignored."
)


def _entries(folder: str) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(folder) as listing:
            return sorted(listing, key=lambda entry: entry.name)[:MAX_DIR_ENTRIES]
    except OSError:
        return []


def _into_temp(path: str, env: Mapping[str, str]) -> bool:
    target = os.path.join(os.path.dirname(path), os.readlink(path))
    return is_temporary(os.path.normpath(target), env)


def links_into_temp(folder: str, env: Mapping[str, str], levels: int) -> list[str]:
    entries = _entries(folder)
    here = [e.path for e in entries if e.is_symlink() and _into_temp(e.path, env)]
    if levels <= 0:
        return here
    folders = [
        e.path
        for e in entries
        if e.is_dir(follow_symlinks=False) and e.name not in SKIPPED_DIRS
    ]
    return [*here, *(p for f in folders for p in links_into_temp(f, env, levels - 1))]


def _repository(cwd: str, env: Mapping[str, str]) -> str:
    top = probe(["git", "-C", cwd, "rev-parse", "--show-toplevel"]).strip()
    home = env.get("HOME", "")
    return "" if not top or top == home or is_temporary(top, env) else top


def stray_links(cwd: str, env: Mapping[str, str]) -> list[str]:
    home = env.get("HOME", "")
    repo = _repository(cwd, env)
    walked = links_into_temp(repo, env, MAX_DEPTH) if repo else []
    dotfiles = links_into_temp(home, env, 0) if home else []
    config = (
        links_into_temp(str(Path(home, ".config")), env, CONFIG_LEVELS) if home else []
    )
    return sorted({*walked, *dotfiles, *config})


def _message(found: list[str]) -> str:
    rows = [f"  {path} -> {os.readlink(path)}" for path in found[:MAX_REPORTED]]
    return REASON.format(rows="\n".join(rows))


def main() -> int:
    if not should_run(HOOK) or os.environ.get(BYPASS_ENV) == "1" or is_bypassed(HOOK):
        return 0
    payload = read_hook_payload(HOOK)
    found = stray_links(str(payload.get("cwd") or os.getcwd()), os.environ)
    if not found:
        return 0
    message = _message(found)
    if payload.get("stop_hook_active") is True:
        emit_user_notice(message)
        _audit(hook=HOOK, decision="notice", reason="temp links")
        return 0
    sys.stdout.write(json.dumps({"decision": "block", "reason": message}))
    _audit(hook=HOOK, decision="block", reason="temp links")
    return 0


if __name__ == "__main__":
    sys.exit(main())

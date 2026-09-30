#!/usr/bin/env python3
"""Keep a local, never-committed workspace and its continuation prompt.

One hook, three events, dispatched on `hook_event_name`:

  SessionStart  Claim the workspace folder in `.git/info/exclude` and release
                any folder the project has since started tracking. Silent.
  Stop          Block once when `<root>/PROMPT.md` is older than the newest
                change, so the turn ends with a prompt a new session can use.
  PreToolUse    On Bash, refuse `git add --force` that would stage the
                workspace. A plain add of an excluded path is refused by git.

The workspace root is `docs/` unless the project owns it, then `.work/`.
Resolution lives in `_lib/project_workspace.py`.

Fail closed: when git cannot answer, a forced add is blocked, SessionStart
writes nothing, and Stop allows the stop and logs the error.

Bypass: PROJECT_WORKSPACE_DISABLE=1 in the parent shell, or the bypass
registry entry `project-workspace`.
Enforces: rules/project-workspace.md.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

from _lib import project_workspace as pw  # noqa: E402
from _lib.audit_log import record as _audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402

HOOK_NAME = "project-workspace"
ADD_COMMANDS = frozenset({"add", "stage"})
GIT_OPTIONS_WITH_VALUE = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
)
SEGMENT_BREAK = re.compile(r"^[;&|]+$")
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
GLOB_CHARS = re.compile(r"[*?\[]")
UNPARSEABLE_FORCED_ADD = re.compile(
    r"\bgit\b.*\b(?:add|stage)\b.*(?:\s-[A-Za-z]*f|--force)"
)


@dataclass(frozen=True, slots=True)
class ForcedAdd:
    base: Path
    paths: tuple[str, ...]


def _log(message: str) -> None:
    sys.stderr.write(f"{HOOK_NAME}: {message}\n")


def _segments(command: str) -> list[list[str]]:
    segments: list[list[str]] = []
    for line in command.splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        current: list[str] = []
        for token in lexer:
            if SEGMENT_BREAK.match(token):
                segments.append(current)
                current = []
            else:
                current.append(token)
        segments.append(current)
    return [segment for segment in segments if segment]


def _split_git_prefix(tokens: list[str], cwd: Path) -> tuple[Path, list[str]] | None:
    rest = tokens[_first_command_index(tokens) :]
    if not rest or Path(rest[0]).name != "git":
        return None
    base, index = cwd, 1
    while index < len(rest) and rest[index].startswith("-"):
        if rest[index] in GIT_OPTIONS_WITH_VALUE and index + 1 < len(rest):
            base = base / rest[index + 1] if rest[index] == "-C" else base
            index += 1
        index += 1
    return base, rest[index:]


def _first_command_index(tokens: list[str]) -> int:
    for index, token in enumerate(tokens):
        if not ENV_ASSIGNMENT.match(token):
            return index
    return len(tokens)


def _is_force(arg: str) -> bool:
    if arg == "--force":
        return True
    return arg.startswith("-") and not arg.startswith("--") and "f" in arg[1:]


def _forced_add(tokens: list[str], cwd: Path) -> ForcedAdd | None:
    split = _split_git_prefix(tokens, cwd)
    if split is None or not split[1] or split[1][0] not in ADD_COMMANDS:
        return None
    base, args = split[0], split[1][1:]
    marker = args.index("--") if "--" in args else len(args)
    options, trailing = args[:marker], args[marker + 1 :]
    if not any(_is_force(arg) for arg in options):
        return None
    paths = tuple(a for a in options if not a.startswith("-")) + tuple(trailing)
    return ForcedAdd(base=base, paths=paths or (".",))


def _target(base: Path, top: Path, spec: str) -> Path:
    if spec.startswith(":"):
        return top
    match = GLOB_CHARS.search(spec)
    if match is None:
        return (base / spec).resolve()
    return (base / spec[: match.start()].rpartition("/")[0]).resolve()


def _overlaps(target: Path, workspace: Path) -> bool:
    return (
        target == workspace
        or workspace in target.parents
        or target in workspace.parents
    )


def _workspace_hit(add: ForcedAdd) -> str | None:
    top = pw.toplevel(add.base)
    if top is None:
        return None
    root = pw.resolve_root(top)
    workspace = top / root
    hits = [
        spec for spec in add.paths if _overlaps(_target(add.base, top, spec), workspace)
    ]
    return f"{root}/" if hits else None


def _deny(reason: str, command: str) -> int:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stderr.write(reason)
    _audit(
        hook=HOOK_NAME,
        decision="block",
        decision_class="block",
        reason=reason[:200],
        tool="Bash",
        command_excerpt=command[:200],
    )
    return 2


def _stage_reason(root: str) -> str:
    return (
        f"BLOCKED: this forced add would stage the local workspace `{root}`.\n"
        f"The workspace holds working material and PROMPT.md and is never committed.\n"
        f"Rule: ~/.claude/rules/project-workspace.md.\n"
        f"Fix: name the project paths explicitly, without `{root}`.\n"
        f"Bypass (one-off): PROJECT_WORKSPACE_DISABLE=1 in the parent shell."
    )


def _command(data: dict[str, object]) -> str:
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    return str(tool_input.get("command") or "")


def handle_stage(data: dict[str, object], cwd: Path) -> int:
    command = _command(data)
    try:
        adds = [a for s in _segments(command) if (a := _forced_add(s, cwd))]
    except ValueError:
        if UNPARSEABLE_FORCED_ADD.search(command):
            return _deny(_stage_reason("docs/ or .work/"), command)
        return 0
    for add in adds:
        try:
            hit = _workspace_hit(add)
        except pw.WorkspaceError as exc:
            return _deny(
                f"BLOCKED: forced add, and git could not resolve the workspace: {exc}",
                command,
            )
        if hit:
            return _deny(_stage_reason(hit), command)
    return 0


def handle_start(cwd: Path) -> int:
    try:
        top = pw.toplevel(cwd)
        if top is None:
            return 0
        pw.release_tracked(top)
        root = pw.resolve_root(top)
        pw.ensure_excluded(top, root)
    except (pw.WorkspaceError, OSError) as exc:
        _log(f"workspace not claimed: {exc}")
    return 0


def _stop_reason(root: str) -> str:
    return (
        f"{root}/PROMPT.md is older than the newest change in this repository. "
        f"Rewrite it before ending the turn, per ~/.claude/standards/project-workspace.md: "
        f"what the project is with a pointer to the README, what to read first, the hard "
        f"constraints, a dated state, the numbered next steps, and what was decided against. "
        f"It must be pasteable into a new session with no other context."
    )


def handle_stop(data: dict[str, object], cwd: Path) -> int:
    if data.get("stop_hook_active") is True:
        return 0
    try:
        top = pw.toplevel(cwd)
        if top is None:
            return 0
        root = pw.resolve_root(top)
        stale = pw.prompt_is_stale(top, root)
    except (pw.WorkspaceError, OSError) as exc:
        _log(f"prompt freshness not checked: {exc}")
        return 0
    if stale:
        sys.stdout.write(
            json.dumps({"decision": "block", "reason": _stop_reason(root)})
        )
        _audit(
            hook=HOOK_NAME,
            decision="block",
            decision_class="block",
            reason="stale prompt",
        )
    return 0


def main() -> int:
    if os.environ.get("PROJECT_WORKSPACE_DISABLE") == "1" or is_bypassed(HOOK_NAME):
        return 0
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(data, dict):
        return 0
    cwd = Path(str(data.get("cwd") or os.getcwd()))
    event = data.get("hook_event_name")
    if event == "SessionStart":
        return handle_start(cwd)
    if event == "Stop":
        return handle_stop(data, cwd)
    if event == "PreToolUse" and data.get("tool_name") == "Bash":
        return handle_stage(data, cwd)
    return 0


if __name__ == "__main__":
    sys.exit(main())

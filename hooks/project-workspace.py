#!/usr/bin/env python3
"""Keep a local, never-committed workspace and its continuation prompt.

One hook, three events, dispatched on `hook_event_name`:

  SessionStart  Claim the workspace folder in `.git/info/exclude` and release
                any folder the project has since started tracking. Silent.
  Stop          Block once when `<root>/PROMPT.md` is older than the newest
                change, so the turn ends with a prompt a new session can use.
  PreToolUse    On Bash, refuse `git add --force` that would stage the
                workspace, and refuse any add or commit that would put a file
                named PROMPT.md, at any depth and in any case, under version
                control. SessionStart also excludes PROMPT.md locally.

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
UNPARSEABLE_PROMPT = re.compile(
    r"\bgit\b.*\b(?:add|stage|commit)\b.*prompt\.md", re.IGNORECASE
)
ADD_ALL_FLAGS = frozenset({"-A", "--all", "--no-ignore-removal"})
ADD_UPDATE_FLAGS = frozenset({"-u", "--update"})
COMMIT_VALUE_SHORT = frozenset("mFCct")
COMMIT_VALUE_LONG = frozenset(
    {
        "--message",
        "--file",
        "--author",
        "--date",
        "--template",
        "--reuse-message",
        "--reedit-message",
        "--fixup",
        "--squash",
        "--cleanup",
        "--trailer",
        "--pathspec-from-file",
    }
)


@dataclass(frozen=True, slots=True)
class GitCall:
    base: Path
    subcommand: str
    args: tuple[str, ...]


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


def _git_call(tokens: list[str], cwd: Path) -> GitCall | None:
    split = _split_git_prefix(tokens, cwd)
    if split is None or not split[1]:
        return None
    return GitCall(base=split[0], subcommand=split[1][0], args=tuple(split[1][1:]))


def _split_dashdash(args: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    marker = args.index("--") if "--" in args else len(args)
    return args[:marker], args[marker + 1 :]


def _forced_add(call: GitCall) -> ForcedAdd | None:
    if call.subcommand not in ADD_COMMANDS:
        return None
    options, trailing = _split_dashdash(call.args)
    if not any(_is_force(arg) for arg in options):
        return None
    paths = tuple(a for a in options if not a.startswith("-")) + trailing
    return ForcedAdd(base=call.base, paths=paths or (".",))


def _is_short_flag(arg: str, letter: str) -> bool:
    return arg.startswith("-") and not arg.startswith("--") and letter in arg[1:]


def _add_scope(args: tuple[str, ...]) -> tuple[tuple[str, ...], bool]:
    options, trailing = _split_dashdash(args)
    paths = tuple(a for a in options if not a.startswith("-")) + trailing
    tracked_only = any(a in ADD_UPDATE_FLAGS or _is_short_flag(a, "u") for a in options)
    whole = tracked_only or any(
        a in ADD_ALL_FLAGS or _is_short_flag(a, "A") for a in options
    )
    return (paths or ((":/",) if whole else ())), tracked_only


def _short_cluster(letters: str) -> tuple[bool, bool]:
    for index, letter in enumerate(letters):
        if letter in COMMIT_VALUE_SHORT:
            return "a" in letters[:index], index == len(letters) - 1
    return "a" in letters, False


def _commit_scope(args: tuple[str, ...]) -> tuple[str, ...] | None:
    options, trailing = _split_dashdash(args)
    positional: list[str] = []
    whole, skip = False, False
    for arg in options:
        if skip:
            skip = False
        elif arg in COMMIT_VALUE_LONG:
            skip = True
        elif arg.startswith("--"):
            whole = whole or arg == "--all"
        elif arg.startswith("-") and len(arg) > 1:
            has_all, skip = _short_cluster(arg[1:])
            whole = whole or has_all
        else:
            positional.append(arg)
    paths = tuple(positional) + trailing
    return paths or ((":/",) if whole else None)


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


def _prompt_reason(paths: list[str]) -> str:
    return (
        f"BLOCKED: this would put {', '.join(paths)} under version control.\n"
        f"PROMPT.md is the local session hand-off and is never committed, in any "
        f"repository, at any depth.\n"
        f"Rule: ~/.claude/rules/project-workspace.md.\n"
        f"Fix: leave PROMPT.md out of the add or commit; `git rm --cached <path>` "
        f"stops tracking one that is already committed.\n"
        f"Bypass (one-off): PROJECT_WORKSPACE_DISABLE=1 in the parent shell."
    )


def _workspace_verdict(call: GitCall) -> str | None:
    add = _forced_add(call)
    hit = _workspace_hit(add) if add else None
    return _stage_reason(hit) if hit else None


def _prompt_verdict(call: GitCall) -> str | None:
    if call.subcommand not in ADD_COMMANDS and call.subcommand != "commit":
        return None
    if pw.toplevel(call.base) is None:
        return None
    if call.subcommand == "commit":
        found = pw.prompts_a_commit_would_record(call.base, _commit_scope(call.args))
    else:
        specs, tracked_only = _add_scope(call.args)
        force = any(_is_force(a) for a in _split_dashdash(call.args)[0])
        found = pw.prompts_an_add_would_stage(call.base, specs, force, tracked_only)
    return _prompt_reason(found) if found else None


def _verdict(call: GitCall) -> str | None:
    try:
        return _workspace_verdict(call) or _prompt_verdict(call)
    except pw.WorkspaceError as exc:
        return f"BLOCKED: git {call.subcommand}, and git could not answer: {exc}"


def _unparseable(command: str) -> int:
    if UNPARSEABLE_FORCED_ADD.search(command):
        return _deny(_stage_reason("docs/ or .work/"), command)
    if UNPARSEABLE_PROMPT.search(command):
        return _deny(_prompt_reason(["PROMPT.md"]), command)
    return 0


def handle_stage(data: dict[str, object], cwd: Path) -> int:
    command = _command(data)
    try:
        calls = [c for s in _segments(command) if (c := _git_call(s, cwd))]
    except ValueError:
        return _unparseable(command)
    for call in calls:
        verdict = _verdict(call)
        if verdict:
            return _deny(verdict, command)
    return 0


def handle_start(cwd: Path) -> int:
    try:
        top = pw.toplevel(cwd)
        if top is None:
            return 0
        pw.release_tracked(top)
        root = pw.resolve_root(top)
        pw.ensure_excluded(top, root)
        pw.ensure_pattern_excluded(top, pw.PROMPT_NAME)
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

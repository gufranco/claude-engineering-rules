#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


INTERACTIVE_PRONE = ("rm", "cp", "mv")
MAKE_COMMANDS = ("make", "gmake")
MAKEFILE_NAMES = ("GNUmakefile", "makefile", "Makefile")
COVERAGE_TARGET = "coverage"
MAKEFILE_READ_LIMIT = 1_000_000
KCOV_REASON = (
    "BLOCKED: kcov on macOS. Homebrew kcov 43 traces bash through stderr here, "
    "which has held 44 GB and run 74 minutes, and its number is wrong: "
    "76.89% on macOS where Linux measures 98.74%.\n"
    "Fix: measure in Linux the way CI does. Pipe the committed tree into a "
    "container, `git archive HEAD | docker run --rm -i --memory=2g ubuntu:26.04 "
    "bash -c '...'`, install bats, tmux, make, python3 and the kcov build "
    "dependencies, build kcov from source, and run `make coverage` as a "
    "non-root user. Or push and read the CI coverage job.\n"
    "Bypass (one-off): set INTERACTIVE_CMD_DISABLE=1 in parent shell."
)

MAME_COMMANDS = ("mame", "mame64", "mamearcade")
WINDOW_FLAGS = ("-window", "-w")
NO_WINDOW_PREFIXES = (
    "-list",
    "-verify",
    "-help",
    "-showusage",
    "-showconfig",
    "-createconfig",
    "-romident",
    "-validate",
    "-version",
)
HEADLESS_DRIVER = "SDL_VIDEODRIVER=dummy"
WATCHED_MARK = "MAME_WATCHED=1"
MAME_REASON = (
    "BLOCKED: MAME launched {fault}. MAME opens full screen on macOS by default, "
    "which takes the user's display while they work, and `-video none` alone "
    "still opens an SDL window.\n"
    "Fix: run it headless, `SDL_VIDEODRIVER=dummy mame -window -video none "
    "-sound none ...`. When the user asked to watch the run, mark it "
    "`MAME_WATCHED=1 mame -window -nomaximize ...` and minimise it. Prefer "
    "another emulator for the evidence: MAME's BIOS and configuration "
    "defaults produce failures and false positives.\n"
    "Bypass (one-off): set INTERACTIVE_CMD_DISABLE=1 in parent shell."
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.shell_segments import command_head, quoted_segments  # noqa: E402


def has_force_flag(tokens: list[str]) -> bool:
    for tok in tokens[1:]:
        if not tok.startswith("-"):
            continue
        if tok == "--force":
            return True
        if tok.startswith("--"):
            continue
        if "f" in tok[1:]:
            return True
    return False


def bypasses_alias(tokens: list[str]) -> bool:
    words = [token for token in tokens if "=" not in token or token.startswith("-")]
    return bool(words) and words[0] == "command"


def is_blocked(command: str) -> tuple[bool, str]:
    for tokens in quoted_segments(command):
        base, effective = command_head(tokens)
        if base not in INTERACTIVE_PRONE or bypasses_alias(tokens):
            continue
        if not has_force_flag(effective):
            return True, base
    return False, ""


def make_dir_and_files(args: list[str], cwd: str) -> tuple[str, list[str]]:
    directory = cwd
    files: list[str] = []
    for flag, value in zip(args, args[1:]):
        if flag == "-C":
            directory = os.path.join(directory, os.path.expanduser(value))
        elif flag == "-f":
            files = [*files, value]
    return directory, files or list(MAKEFILE_NAMES)


def makefile_uses_kcov(directory: str, names: list[str]) -> bool:
    for name in names:
        path = os.path.join(directory, name)
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                return "kcov" in handle.read(MAKEFILE_READ_LIMIT)
        except OSError:
            continue
    return False


def runs_kcov(base: str, args: list[str], cwd: str) -> bool:
    if base == "kcov":
        return True
    if base not in MAKE_COMMANDS or COVERAGE_TARGET not in args[1:]:
        return False
    directory, names = make_dir_and_files(args[1:], cwd)
    return makefile_uses_kcov(directory, names)


def kcov_blocked(command: str, cwd: str, platform: str) -> bool:
    if platform != "darwin":
        return False
    current = cwd
    for tokens in quoted_segments(command):
        base, args = command_head(tokens)
        if base == "cd" and len(args) > 1:
            current = os.path.join(current, os.path.expanduser(args[1]))
            continue
        if runs_kcov(base, args, current):
            return True
    return False


def flag_value(args: list[str], flag: str) -> str:
    following = [value for name, value in zip(args, args[1:]) if name == flag]
    return following[-1] if following else ""


def headless_gaps(args: list[str], env: frozenset[str]) -> list[str]:
    wanted = (
        (HEADLESS_DRIVER in env, HEADLESS_DRIVER),
        (flag_value(args, "-video") == "none", "-video none"),
        (flag_value(args, "-sound") == "none", "-sound none"),
    )
    return [name for present, name in wanted if not present]


def mame_fault(tokens: list[str], exported: frozenset[str]) -> str:
    base, args = command_head(tokens)
    if base not in MAME_COMMANDS or any(
        arg.startswith(NO_WINDOW_PREFIXES) for arg in args[1:]
    ):
        return ""
    env = exported | frozenset(tokens[: len(tokens) - len(args)])
    if not set(WINDOW_FLAGS) & set(args):
        return "without `-window`"
    if WATCHED_MARK in env:
        return "" if "-nomaximize" in args else "watched without `-nomaximize`"
    gaps = headless_gaps(args, env)
    return f"without {', '.join(f'`{gap}`' for gap in gaps)}" if gaps else ""


def mame_blocked(command: str) -> str:
    exported: frozenset[str] = frozenset()
    for tokens in quoted_segments(command):
        base, args = command_head(tokens)
        if base == "export":
            exported = exported | frozenset(args[1:])
            continue
        fault = mame_fault(tokens, exported)
        if fault:
            return fault
    return ""


def emit_block(reason: str, command: str) -> None:
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
        hook="interactive-cmd-blocker",
        decision="block",
        decision_class="block",
        reason=reason[:200],
        tool="Bash",
        command_excerpt=command[:200],
    )
    sys.exit(2)


def _force_flag_reason(base: str) -> str:
    return (
        f"BLOCKED: `{base}` invoked without `-f`. On macOS this often hangs "
        f"because the default alias adds `-i` and prompts for confirmation "
        f"that the agent cannot answer.\n"
        f"Fix: add `-f` (e.g. `{base} -f <path>` or `{base} -rf <path>` for "
        f"directories).\n"
        f"Bypass (one-off): set INTERACTIVE_CMD_DISABLE=1 in parent shell."
    )


def main() -> int:
    if os.environ.get("INTERACTIVE_CMD_DISABLE") == "1":
        return 0
    if is_bypassed("interactive-cmd-blocker"):
        return 0

    data = read_hook_payload("interactive-cmd-blocker")

    if data.get("tool_name") != "Bash":
        return 0

    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    cwd = data.get("cwd") or os.getcwd()
    if kcov_blocked(command, cwd, sys.platform):
        emit_block(KCOV_REASON, command)

    fault = mame_blocked(command)
    if fault:
        emit_block(MAME_REASON.format(fault=fault), command)

    blocked, base = is_blocked(command)
    if not blocked:
        return 0

    emit_block(_force_flag_reason(base), command)
    return 2


if __name__ == "__main__":
    sys.exit(main())

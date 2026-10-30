#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.audit_log import record as _audit_record  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.output import block as _block  # noqa: E402
from _lib.shell_segments import command_head, operator_segments  # noqa: E402

HOOK_NAME = "background-exit-status"
ENV_DISABLE = "BACKGROUND_EXIT_STATUS_DISABLE"
GROUPING = "(){} \t\n"
PIPE_OPERATORS = frozenset({"|", "|&"})
PIPEFAIL = re.compile(r"\bpipefail\b")
REPORTERS = frozenset(
    {
        ":",
        "awk",
        "cat",
        "column",
        "cut",
        "date",
        "du",
        "echo",
        "egrep",
        "fgrep",
        "grep",
        "head",
        "jq",
        "ls",
        "printf",
        "rg",
        "sed",
        "sort",
        "tail",
        "tee",
        "true",
        "uniq",
        "wc",
    }
)
SETUP = frozenset(
    {"", ".", "cd", "export", "popd", "pushd", "set", "source", "ulimit", "umask"}
)


def _head(text: str) -> str:
    line = text.strip(GROUPING).split("\n", 1)[0]
    try:
        tokens = shlex.split(line)
    except ValueError:
        tokens = line.split()
    name, _ = command_head(tokens)
    return name


def _last_statement_start(operators: list[str]) -> int:
    return max(
        (i for i, op in enumerate(operators) if op not in PIPE_OPERATORS), default=0
    )


def find_masking_reporter(command: str) -> str | None:
    segments = [
        (text, op) for text, op in operator_segments(command) if text.strip(GROUPING)
    ]
    heads = [_head(text) for text, _ in segments]
    statement = heads[_last_statement_start([op for _, op in segments]) :]
    measured = [head for head in heads[:-1] if head not in REPORTERS | SETUP]
    if not measured or statement[0] == "exit" or statement[-1] not in REPORTERS:
        return None
    if (
        len(statement) > 1
        and statement[0] not in REPORTERS
        and PIPEFAIL.search(command)
    ):
        return None
    return statement[-1]


def _message(reporter: str) -> str:
    return _block(
        hook=HOOK_NAME,
        rule_anchor="rules/agent-operating-limits.md",
        detected=(
            f"A background command ends in `{reporter}`, after the step it runs.\n"
            f"The task notification reports the exit status of `{reporter}`, not of that step."
        ),
        why=(
            "A background task is judged by its notification. When a filter or a report "
            "runs last, a failed build or test suite is announced as exit code 0."
        ),
        fix=(
            "End on the measured step, or carry its status to the end:\n"
            "  cmd > log 2>&1; code=$?; tail -n 20 log; exit $code\n"
            "For a pipeline, start the command with `set -o pipefail`."
        ),
        bypass_when="The command measures nothing, such as a log follow after a build.",
        decision="FIX-AND-RETRY",
        env_var=ENV_DISABLE,
    )


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1" or is_bypassed(HOOK_NAME):
        return 0
    if not should_run(HOOK_NAME):
        return 0
    tool_input = tool_input_of(read_hook_payload(HOOK_NAME))
    command = str(tool_input.get("command") or "")
    if tool_input.get("run_in_background") is not True:
        return 0
    reporter = find_masking_reporter(command)
    if reporter is None:
        return 0
    sys.stderr.write(_message(reporter))
    _audit_record(
        hook=HOOK_NAME,
        decision="block",
        decision_class="block",
        reason=f"background command ends in {reporter}",
        tool="Bash",
        command_excerpt=command[:200],
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

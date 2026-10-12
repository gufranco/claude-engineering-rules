from __future__ import annotations

import re

SHELL_WORD = (
    r"""(?:'[^']*'|"(?:[^"\\]|\\.)*"|\$\([^()]*\)|`[^`]*`|\\.|[^\s'"\\;&|()<>`])+"""
)

OPTIONS_WITH_SEPARATE_VALUE = (
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--config-env",
    "--attr-source",
)

OPTIONS_WITH_INLINE_VALUE = (
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--config-env",
    "--attr-source",
    "--exec-path",
    "--super-prefix",
    "--list-cmds",
)

FLAG_OPTIONS = (
    "-p",
    "-P",
    "--paginate",
    "--no-pager",
    "--bare",
    "--no-replace-objects",
    "--literal-pathspecs",
    "--glob-pathspecs",
    "--noglob-pathspecs",
    "--icase-pathspecs",
    "--no-optional-locks",
    "--no-advice",
    "--no-lazy-fetch",
    "--exec-path",
)


def _alternation(options: tuple[str, ...]) -> str:
    return "|".join(re.escape(option) for option in options)


GLOBAL_OPTION = (
    rf"(?:(?:{_alternation(OPTIONS_WITH_SEPARATE_VALUE)})\s+{SHELL_WORD}"
    rf"|(?:{_alternation(OPTIONS_WITH_INLINE_VALUE)})={SHELL_WORD}"
    rf"|(?:{_alternation(FLAG_OPTIONS)}))(?=\s|$)"
)

PUSH_SEGMENT = r"\bgit\s+push\b[^;&|\n]*?\s"
FLAG_END = r"(?=$|[\s;&|)'\"])"
FORCE_PUSH_LONG = rf"{PUSH_SEGMENT}--force{FLAG_END}"
FORCE_PUSH_SHORT = rf"{PUSH_SEGMENT}-[a-zA-Z]*f[a-zA-Z]*{FLAG_END}"
FORCE_PUSH_WITH_LEASE = rf"{PUSH_SEGMENT}--force-with-lease(?:=\S*)?{FLAG_END}"

GIT_WITH_GLOBAL_OPTIONS = re.compile(rf"(?<![\w.-])(git)(?:\s+{GLOBAL_OPTION})+")


def strip_git_global_options(command: str) -> str:
    return GIT_WITH_GLOBAL_OPTIONS.sub(lambda match: match.group(1), command)

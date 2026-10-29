from __future__ import annotations

import re

from _lib.cli_invocations import Invocation, invocations, segments

PROBES = frozenset({"--version", "-v", "help", "--help", "-h"})
PIP_INSTALL = re.compile(r"^(?:\S*/)?(?:pip3?|python3?\s+-m\s+pip)\s+install\b")
PIP_ADVICE = "pip install: use uv add, uv sync or uv tool install"
NPM_REPLACEMENTS = {
    "ci": "pnpm install --frozen-lockfile",
    "i": "pnpm install",
    "install": "pnpm install",
}


def _probe(call: Invocation) -> bool:
    return not call.args or call.args[0] in PROBES


def _npm(call: Invocation) -> str:
    verb, rest = call.args[0], " ".join(call.args[1:2])
    shown = f"npm {verb} {rest}".rstrip()
    replacement = NPM_REPLACEMENTS.get(verb, f"pnpm {verb} {rest}".rstrip())
    return f"{shown}: use {replacement}"


def _npx(call: Invocation) -> str:
    return f"npx {call.args[0]}: use pnpm exec {call.args[0]}"


def _yarn(call: Invocation) -> str:
    shown = " ".join(call.args[:2])
    return f"yarn {shown}: use pnpm {shown}"


FORMATTERS = (("npm", _npm), ("npx", _npx), ("yarn", _yarn))


def violations(command: str) -> list[str]:
    node = [
        format_call(call)
        for binary, format_call in FORMATTERS
        for call in invocations(command, binary)
        if not _probe(call)
    ]
    pip = [PIP_ADVICE for part in segments(command) if PIP_INSTALL.match(part)]
    return [*node, *pip]

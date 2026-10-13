from __future__ import annotations

import os
import re
from dataclasses import dataclass

from _lib.shell_segments import mask_literal_text

SUBSTITUTION = re.compile(r"\$\([^()]*\)|`[^`\n]*`")
SEPARATOR = re.compile(r"&&|\|\||[;|&\n]")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=\S*")
PREFIX_WORDS = frozenset({"env", "command", "exec", "builtin", "nohup", "time"})


@dataclass(frozen=True, slots=True)
class Invocation:
    binary: str
    assigned: frozenset[str]
    args: tuple[str, ...]


def segments(command: str) -> list[str]:
    flat = SUBSTITUTION.sub("SUBST", mask_literal_text(command))
    return [part.strip() for part in SEPARATOR.split(flat) if part.strip()]


def _split_prefix(words: list[str]) -> tuple[frozenset[str], list[str]]:
    names: frozenset[str] = frozenset()
    index = 0
    while index < len(words):
        word = words[index]
        if ASSIGNMENT.fullmatch(word):
            names = names | {word.split("=", 1)[0]}
        elif word not in PREFIX_WORDS:
            break
        index += 1
    return names, words[index:]


def _exported_names(words: list[str]) -> frozenset[str]:
    if words[:1] != ["export"]:
        return frozenset()
    return frozenset(w.split("=", 1)[0] for w in words[1:] if ASSIGNMENT.fullmatch(w))


def invocations(command: str, binary: str) -> list[Invocation]:
    exported: frozenset[str] = frozenset()
    found: list[Invocation] = []
    for part in segments(command):
        words = part.split()
        exported = exported | _exported_names(words)
        assigned, rest = _split_prefix(words)
        if rest and os.path.basename(rest[0]) == binary:
            found = [*found, Invocation(binary, assigned | exported, tuple(rest[1:]))]
    return found

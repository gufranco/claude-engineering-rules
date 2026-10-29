from __future__ import annotations

import os
import re
from collections.abc import Mapping

ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.DOTALL)
REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def expand(value: str, known: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        found = known.get(name, os.environ.get(name))
        return match.group(0) if found is None else found

    return REFERENCE.sub(replace, os.path.expanduser(value))


def assignments(segment: list[str], known: Mapping[str, str]) -> dict[str, str] | None:
    words = segment[1:] if segment[:1] == ["export"] else segment
    pairs = [pair for word in words if (pair := ASSIGNMENT.fullmatch(word))]
    if not words or len(pairs) != len(words):
        return None
    found = dict(known)
    for pair in pairs:
        found = {**found, pair.group(1): expand(pair.group(2), found)}
    return found

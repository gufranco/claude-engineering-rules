#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.guard_runner import Edit, Finding, GuardSpec, run_guard  # noqa: E402
from _lib.python_mutation_detectors import find, is_python_source  # noqa: E402

WHY = (
    "A mutable default is created once at definition time, so every call shares it.\n"
    "A mutated parameter changes a value the caller still holds, and nothing at the\n"
    "call site shows that it happened. Module and class level containers are shared\n"
    "by every caller and every instance, so a write there is a hidden global.\n"
    "See ~/.claude/standards/immutability.md."
)

FIX = (
    "  - Mutable default: use `None` and build a fresh value inside the function.\n"
    "  - Mutated parameter: return a new value, `(*items, tag)`, `{**meta, k: v}`,\n"
    "    `dataclasses.replace(obj, k=v)`, or copy first with `items = list(items)`.\n"
    "  - Module state or `global`: pass state in and return the new state.\n"
    "  - Class attribute: annotate `ClassVar[...]` with a tuple or frozenset, or\n"
    "    build it per instance in `__init__` or `field(default_factory=...)`.\n"
    "  - Value types: `@dataclass(frozen=True, slots=True)`.\n"
    "  - Accept read-only types at the boundary: `Sequence`, `Mapping`, `tuple`."
)

BYPASS_WHEN = (
    "The function is documented as an in-place operation whose whole contract is the\n"
    "mutation, such as a buffer writer in a measured hot path. Prefer a `# noqa`\n"
    "comment on that line naming the reason over disabling the hook."
)


def _find(edit: Edit) -> tuple[Finding, ...]:
    return find(edit.text)


SPEC = GuardSpec(
    hook_id="python-mutation-guard",
    env_disable="PYTHON_MUTATION_DISABLE",
    rule_anchor="standards/immutability.md#per-language-expression",
    intro="Mutation of shared or caller-owned state:",
    why=WHY,
    fix=FIX,
    bypass_when=BYPASS_WHEN,
    safety="callers keep seeing state change under them.",
    reason="python mutation",
    applies_to=is_python_source,
    find=_find,
)


if __name__ == "__main__":
    sys.exit(run_guard(SPEC))

#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import PurePosixPath

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.guard_runner import Edit, Finding, GuardSpec, run_guard  # noqa: E402
from _lib.polyglot_mutation_jvm import JVM_FINDERS  # noqa: E402
from _lib.polyglot_mutation_native import NATIVE_FINDERS  # noqa: E402
from _lib.polyglot_mutation_scripting import find_lua, find_ruby  # noqa: E402
from _lib.source_scope import in_scope  # noqa: E402

FINDERS = {**NATIVE_FINDERS, **JVM_FINDERS, ".rb": find_ruby, ".lua": find_lua}

WHY = (
    "Shared mutable state is the source of aliasing bugs and data races: a value one\n"
    "part of the program still holds changes under it, and a static or package-level\n"
    "container is shared by every caller and every thread. The language has an\n"
    "immutable form for each finding below. See ~/.claude/standards/immutability.md."
)

FIX = (
    "  - Go: pass state in and return the new value; `slices.Clone` before `append`.\n"
    "  - Rust: atomics, `Mutex`, `OnceLock` or `LazyLock` instead of `static mut`.\n"
    "  - Java: `static final` with `List.of`, `Map.of` or `List.copyOf`; prefer records.\n"
    "  - Kotlin: `val`, `copy()`, and read-only `List`, `Map`, `Set` in public API.\n"
    "  - C#: `readonly record struct`, `init` accessors, `static readonly`.\n"
    "  - Dart: `final` fields, `const` constructors, `@freezed`.\n"
    "  - Ruby: `# frozen_string_literal: true` and `.freeze` on constants.\n"
    "  - C and C++: `static const` or `constexpr` tables, which also move them to ROM.\n"
    "  - Lua: `local`, and `<const>` on Lua 5.4."
)

BYPASS_WHEN = (
    "The state is genuinely shared by design, such as a hardware register map or a\n"
    "DMA buffer. Prefer the language's own suppression comment on that line, such as\n"
    "`// NOLINT`, `#[allow(...)]`, `@Suppress(...)` or `# rubocop:disable`, naming why."
)


def applies_to(path: str) -> bool:
    return PurePosixPath(path.lower()).suffix in FINDERS and in_scope(path)


def find(edit: Edit) -> tuple[Finding, ...]:
    return FINDERS[PurePosixPath(edit.path.lower()).suffix](edit)


SPEC = GuardSpec(
    hook_id="polyglot-immutability-guard",
    env_disable="POLYGLOT_IMMUTABILITY_DISABLE",
    rule_anchor="standards/immutability.md#per-language-expression",
    intro="Shared mutable state:",
    why=WHY,
    fix=FIX,
    bypass_when=BYPASS_WHEN,
    safety="aliasing bugs and data races ship in code that reads as safe.",
    reason="polyglot mutation",
    applies_to=applies_to,
    find=find,
)


if __name__ == "__main__":
    sys.exit(run_guard(SPEC))

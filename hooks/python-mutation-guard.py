#!/usr/bin/env python3
"""
python-mutation-guard.py

PreToolUse hook that enforces the immutability baseline in Python.
Rule source: ~/.claude/standards/immutability.md "Per-Language Expression",
~/.claude/rules/lang/python.md, ~/.claude/rules/code-style.md "Immutability".

mutation-method-blocker.py covers TypeScript and is built around TypeScript
semantics: the ES2024 replacement tables, framework allowlists such as Immer and
Zustand, the TS project service, and source-map remapping. None of that transfers
to Python, so Python gets its own detector set here and shares the same
infrastructure through `_lib`: bypass channels, audit trail, block schema,
suppression, and profile gating.

Two detections, both parsed with `ast` rather than matched with regex:

  1. Mutable default argument. `def f(items=[])` shares one list across every
     call, so the second caller sees what the first appended.

  2. Parameter mutation. A function that mutates its argument changes a value the
     caller still holds, and the change is invisible at the call site. The message
     names the read-only annotation when one is present, since mutating a value
     typed `Sequence` or `Mapping` is also a type error the checker should catch.

`self` and `cls` are exempt: mutating instance state is what methods are for.
Local accumulators are exempt: the value never leaves the function.

Skipped: test files, migrations, and this repo's own hooks.

Modes:
  default                    warn only, exit 0
  PYTHON_MUTATION_ENFORCE=1  block, exit 2

Bypass:
  PYTHON_MUTATION_DISABLE=1
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


try:
    from _lib.suppression import line_or_prev_has_suppression  # type: ignore
except Exception:  # pragma: no cover

    def line_or_prev_has_suppression(lines, line_no):  # type: ignore
        return False


try:
    from _lib.bypass import is_bypassed  # type: ignore
except Exception:  # pragma: no cover

    def is_bypassed(_hook: str) -> bool:  # type: ignore
        return False


try:
    from _lib.hook_profile import should_run  # type: ignore
except Exception:  # pragma: no cover

    def should_run(_id: str) -> bool:  # type: ignore
        return True


from _lib.output import block, warn  # noqa: E402

HOOK_ID = "python-mutation-guard"
ENV_DISABLE = "PYTHON_MUTATION_DISABLE"
ENV_ENFORCE = "PYTHON_MUTATION_ENFORCE"

SKIP_SUFFIXES = ("_test.py", "_tests.py", ".pyi")
SKIP_PREFIXES = ("test_",)
SKIP_SEGMENTS = (
    "/tests/",
    "/test/",
    "/__tests__/",
    "/migrations/",
    "/migration/",
    "/fixtures/",
    "/.claude/hooks/",
    "/site-packages/",
)

MUTATING_METHODS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "remove",
        "pop",
        "clear",
        "sort",
        "reverse",
        "update",
        "add",
        "discard",
        "setdefault",
        "popitem",
        "appendleft",
        "extendleft",
    }
)

READ_ONLY_ANNOTATIONS = frozenset(
    {
        "Sequence",
        "Mapping",
        "AbstractSet",
        "Collection",
        "Iterable",
        "FrozenSet",
        "frozenset",
        "tuple",
        "Tuple",
    }
)

EXEMPT_PARAMS = frozenset({"self", "cls"})

MUTABLE_DEFAULT_CALLS = frozenset({"list", "dict", "set", "bytearray", "defaultdict"})

MUTABLE_DEFAULT_REGEX = re.compile(
    r"def\s+\w+\s*\([^)]*?=\s*(?:\[\s*\]|\{\s*\}|set\s*\(\s*\)|list\s*\(\s*\)|dict\s*\(\s*\))",
    re.DOTALL,
)

MAX_FINDINGS = 8


def is_skipped(path: str) -> bool:
    if not path:
        return True
    lowered = path.lower()
    if not lowered.endswith(".py"):
        return True
    if any(lowered.endswith(suffix) for suffix in SKIP_SUFFIXES):
        return True
    if any(segment in lowered for segment in SKIP_SEGMENTS):
        return True
    basename = lowered.rsplit("/", 1)[-1]
    if any(basename.startswith(prefix) for prefix in SKIP_PREFIXES):
        return True
    return False


def collect(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    path = tool_input.get("file_path", "") or ""
    items: list[tuple[str, str]] = []
    if tool == "Write":
        content = tool_input.get("content", "")
        if isinstance(content, str):
            items.append((path, content))
    elif tool == "Edit":
        content = tool_input.get("new_string", "")
        if isinstance(content, str):
            items.append((path, content))
    elif tool == "MultiEdit":
        for edit in tool_input.get("edits", []) or []:
            if isinstance(edit, dict):
                content = edit.get("new_string", "")
                if isinstance(content, str):
                    items.append((path, content))
    return items


def annotation_name(node: ast.expr | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return annotation_name(node.value)
    if isinstance(node, ast.BinOp):
        return annotation_name(node.left) or annotation_name(node.right)
    return ""


def is_mutable_default(node: ast.expr) -> bool:
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    if isinstance(node, ast.Call):
        return annotation_name(node.func) in MUTABLE_DEFAULT_CALLS
    return False


def parameters_of(func: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
    args = func.args
    everything = [
        *args.posonlyargs,
        *args.args,
        *args.kwonlyargs,
    ]
    if args.vararg:
        everything.append(args.vararg)
    if args.kwarg:
        everything.append(args.kwarg)
    return {
        arg.arg: annotation_name(arg.annotation)
        for arg in everything
        if arg.arg not in EXEMPT_PARAMS
    }


def defaults_of(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.expr]:
    args = func.args
    return [node for node in [*args.defaults, *args.kw_defaults] if node is not None]


def find_in_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]
) -> list[str]:
    hits: list[str] = []
    params = parameters_of(func)

    for default in defaults_of(func):
        if not is_mutable_default(default):
            continue
        if line_or_prev_has_suppression(lines, default.lineno - 1):
            continue
        hits.append(
            f"L{default.lineno}: mutable default argument in `{func.name}`. "
            "One instance is shared by every call"
        )

    for node in ast.walk(func):
        target_name = ""
        line_no = getattr(node, "lineno", 0)

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in MUTATING_METHODS and isinstance(
                node.func.value, ast.Name
            ):
                target_name = node.func.value.id
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(
                    target.value, ast.Name
                ):
                    target_name = target.value.id
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(
                    target.value, ast.Name
                ):
                    target_name = target.value.id

        if not target_name or target_name not in params:
            continue
        if line_or_prev_has_suppression(lines, max(0, line_no - 1)):
            continue

        annotated = params[target_name]
        annotation_note = (
            f", annotated `{annotated}`" if annotated in READ_ONLY_ANNOTATIONS else ""
        )
        hits.append(
            f"L{line_no}: parameter `{target_name}` is mutated inside "
            f"`{func.name}`{annotation_note}"
        )

    return hits


def find(text: str) -> list[str]:
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return find_with_regex(text, lines)

    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            hits.extend(find_in_function(node, lines))

    deduped = list(dict.fromkeys(hits))
    return deduped[:MAX_FINDINGS]


def find_with_regex(text: str, lines: list[str]) -> list[str]:
    """Fallback for Edit fragments that do not parse on their own."""
    hits: list[str] = []
    for match in MUTABLE_DEFAULT_REGEX.finditer(text):
        line_no = text.count("\n", 0, match.start()) + 1
        if line_or_prev_has_suppression(lines, line_no - 1):
            continue
        hits.append(
            f"L{line_no}: mutable default argument. One instance is shared by every call"
        )
    return hits[:MAX_FINDINGS]


DETECTED_INTRO = "Mutation of shared or caller-owned state:"

WHY = (
    "A mutable default is created once at definition time, so every call shares it.\n"
    "A mutated parameter changes a value the caller still holds, and nothing at the\n"
    "call site shows that it happened. See ~/.claude/standards/immutability.md."
)

FIX = (
    "  - Mutable default: use `None` and build a fresh value inside the function.\n"
    "      def collect(items: Sequence[str] | None = None) -> list[str]:\n"
    "          return list(items or ())\n"
    "  - Mutated parameter: return a new value instead.\n"
    "      def add_tag(items: Sequence[str], tag: str) -> tuple[str, ...]:\n"
    "          return (*items, tag)\n"
    "  - Accept the read-only type at the boundary: `Sequence`, `Mapping`,\n"
    "    `AbstractSet`, or `tuple`, so the type checker rejects the mutation too."
)

BYPASS_WHEN = (
    "The function is documented as an in-place operation whose whole contract is the\n"
    "mutation, such as a buffer writer in a measured hot path."
)


def render_findings(findings: list[tuple[str, list[str]]]) -> str:
    lines = [DETECTED_INTRO]
    for path, hits in findings:
        lines.append(f"{path}:")
        lines.extend(f"  {hit}" for hit in hits)
    return "\n".join(lines)


def main() -> int:
    if not should_run(HOOK_ID):
        return 0
    if os.environ.get(ENV_DISABLE) == "1":
        _audit(hook=HOOK_ID, decision="bypass", bypass_env=ENV_DISABLE)
        return 0
    if is_bypassed(HOOK_ID):
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    findings: list[tuple[str, list[str]]] = []
    for path, text in collect(tool, tool_input):
        if is_skipped(path):
            continue
        hits = find(text)
        if hits:
            findings.append((path, hits))

    if not findings:
        return 0

    detected = render_findings(findings)

    if os.environ.get(ENV_ENFORCE) != "1":
        print(
            warn(
                hook=HOOK_ID,
                purpose=f"{detected}\n\n{WHY}\n\n{FIX}",
                next_action=(
                    "Return a fresh value instead of mutating. Set "
                    f"{ENV_ENFORCE}=1 to make this a blocking check."
                ),
            ),
            file=sys.stderr,
        )
        _audit(
            hook=HOOK_ID,
            decision="warn",
            tool=tool,
            reason="python mutation",
            command_excerpt=detected[:240],
        )
        return 0

    print(
        block(
            hook=HOOK_ID,
            rule_anchor="standards/immutability.md#per-language-expression",
            detected=detected,
            why=WHY,
            fix=FIX,
            bypass_when=BYPASS_WHEN,
            decision="FIX-AND-RETRY",
            env_var=ENV_DISABLE,
            safety="callers keep seeing state change under them.",
        ),
        file=sys.stderr,
    )
    _audit(
        hook=HOOK_ID,
        decision="block",
        tool=tool,
        reason="python mutation",
        command_excerpt=detected[:240],
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

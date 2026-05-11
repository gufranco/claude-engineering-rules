"""Lint Claude Code Python hooks for v1/v2 contract compliance.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.4.2.

Two contracts coexist:
  - v1: stderr + `sys.exit(2)`. Block-only behavior.
  - v2: JSON `hookSpecificOutput` envelope on stdout. Adds modify-input,
        ask, defer, and PostToolUse `additionalContext`.

This linter walks `~/.claude/hooks/*.py` and flags two classes of issue:

  1. **Should migrate.** Hooks listed in `decisions.md` D2 (conventional-commits,
     secret-scanner, banned-prose-chars, prisma-schema-sync,
     mutation-method-blocker) that still use raw `sys.exit(2)` instead of
     going through `hook_io.block()` / `hook_io.modify_input()`.

  2. **Inconsistent v1.** Hooks not in the migration list that bypass the
     `hook_io` shim. Adopting the shim is optional for v1 hooks but consistent
     adoption pays off when an audit field or schema change rolls out.

The script never modifies hooks. It exits 0 when no issues are found and 1
otherwise so it can wire into pre-commit and CI.

Usage:

    python3 scripts/hook_contract_lint.py                 # lint all hooks
    python3 scripts/hook_contract_lint.py --format json   # JSON report
    python3 scripts/hook_contract_lint.py --hooks-dir ./hooks
    python3 scripts/hook_contract_lint.py --include foo --include bar
    python3 scripts/hook_contract_lint.py --strict        # treat info as warning
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from typing import Any

DEFAULT_HOOKS_DIR = os.path.expanduser("~/.claude/hooks")
DEFAULT_HOOK_IO_MODULE = "hook_io"

MIGRATION_TARGETS: frozenset[str] = frozenset(
    {
        "conventional-commits",
        "secret-scanner",
        "banned-prose-chars",
        "prisma-schema-sync",
        "mutation-method-blocker",
    }
)

SEVERITIES: tuple[str, ...] = ("info", "warning", "error")


@dataclass(frozen=True)
class Finding:
    """A single contract-lint issue tied to a hook file."""

    hook: str
    path: str
    severity: str
    code: str
    message: str
    line: int = 0


def _hook_basename(path: str) -> str:
    base = os.path.basename(path)
    if base.endswith(".py"):
        base = base[: -len(".py")]
    return base


def _iter_hook_files(hooks_dir: str) -> Iterator[str]:
    if not os.path.isdir(hooks_dir):
        return
    for entry in sorted(os.listdir(hooks_dir)):
        if not entry.endswith(".py"):
            continue
        if entry.startswith("_"):
            continue
        path = os.path.join(hooks_dir, entry)
        if os.path.isfile(path):
            yield path


def _read_source(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _parse_module(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _collect_imports(tree: ast.Module) -> set[str]:
    """Return the set of module names imported anywhere in the file."""
    seen: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                seen.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                seen.add(node.module.split(".")[0])
    return seen


def _find_sys_exit_two_lines(tree: ast.Module) -> list[int]:
    """Return line numbers where `sys.exit(2)` (or equivalent) is called."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        callee = ""
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id == "sys" and func.attr == "exit":
                callee = "sys.exit"
        elif isinstance(func, ast.Name) and func.id == "exit":
            callee = "exit"
        if not callee:
            continue
        if not node.args:
            continue
        first = node.args[0]
        value: Any = None
        if isinstance(first, ast.Constant):
            value = first.value
        if value == 2:
            lines.append(getattr(node, "lineno", 0))
    return sorted(lines)


def _uses_hook_io(imports: set[str]) -> bool:
    return DEFAULT_HOOK_IO_MODULE in imports


def lint_file(path: str) -> list[Finding]:
    """Return findings for a single hook file."""
    source = _read_source(path)
    if not source:
        return []
    tree = _parse_module(source)
    if tree is None:
        return [
            Finding(
                hook=_hook_basename(path),
                path=path,
                severity="error",
                code="HC100",
                message="hook file failed to parse as Python",
            )
        ]

    findings: list[Finding] = []
    hook = _hook_basename(path)
    imports = _collect_imports(tree)
    sys_exit_two = _find_sys_exit_two_lines(tree)
    uses_shim = _uses_hook_io(imports)

    if hook in MIGRATION_TARGETS:
        if not uses_shim:
            findings.append(
                Finding(
                    hook=hook,
                    path=path,
                    severity="error",
                    code="HC001",
                    message=(
                        "hook is listed in decisions.md D2 as a v2 migration target "
                        "but does not import scripts/hook_io.py"
                    ),
                )
            )
        for line in sys_exit_two:
            findings.append(
                Finding(
                    hook=hook,
                    path=path,
                    severity="error",
                    code="HC002",
                    message=(
                        "raw sys.exit(2) found in a v2 migration target; "
                        "use hook_io.block(...) so the v2 envelope can be emitted"
                    ),
                    line=line,
                )
            )
    else:
        if sys_exit_two and not uses_shim:
            findings.append(
                Finding(
                    hook=hook,
                    path=path,
                    severity="info",
                    code="HC010",
                    message=(
                        "hook uses raw sys.exit(2); adopt scripts/hook_io.py for "
                        "consistent audit emission and v2 readiness"
                    ),
                    line=sys_exit_two[0] if sys_exit_two else 0,
                )
            )
    return findings


def lint_directory(
    hooks_dir: str,
    *,
    include: Iterable[str] | None = None,
) -> list[Finding]:
    include_set = set(include) if include else None
    findings: list[Finding] = []
    for path in _iter_hook_files(hooks_dir):
        hook = _hook_basename(path)
        if include_set is not None and hook not in include_set:
            continue
        findings.extend(lint_file(path))
    return findings


def _format_table(findings: list[Finding]) -> str:
    if not findings:
        return "No findings.\n"
    width_hook = max(len(f.hook) for f in findings)
    width_severity = max(len(f.severity) for f in findings)
    lines: list[str] = []
    for f in findings:
        location = f"{f.path}:{f.line}" if f.line else f.path
        lines.append(
            f"{f.severity:<{width_severity}}  {f.code}  "
            f"{f.hook:<{width_hook}}  {f.message}\n  -> {location}"
        )
    return "\n".join(lines) + "\n"


def _format_json(findings: list[Finding]) -> str:
    return (
        json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2) + "\n"
    )


def _exit_code_for(findings: list[Finding], *, strict: bool) -> int:
    if not findings:
        return 0
    threshold = "info" if strict else "warning"
    threshold_idx = SEVERITIES.index(threshold)
    for finding in findings:
        if SEVERITIES.index(finding.severity) >= threshold_idx:
            return 1
    return 0


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Lint Claude Code hooks for v1/v2 contract compliance.",
    )
    parser.add_argument(
        "--hooks-dir",
        default=DEFAULT_HOOKS_DIR,
        help="Directory containing hook *.py files (default: ~/.claude/hooks).",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="Only lint these hook basenames (repeatable).",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat info findings as failing too (default: only warning+error).",
    )
    args = parser.parse_args(argv)

    findings = lint_directory(args.hooks_dir, include=args.include)
    if args.format == "json":
        sys.stdout.write(_format_json(findings))
    else:
        sys.stdout.write(_format_table(findings))
    return _exit_code_for(findings, strict=args.strict)


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))

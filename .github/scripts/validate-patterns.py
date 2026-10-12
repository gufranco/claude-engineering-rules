#!/usr/bin/env python3
"""Validate regex patterns in dangerous-command-blocker.py.

Checks:
  - All regex patterns compile without errors
  - Every uppercase string constant in hooks/_lib/git_invocation.py compiles,
    since the blocker's tables reference those constants by name
  - A table entry that names a constant the lib does not define fails
  - No exact duplicate patterns within or across severity levels
  - Reports total pattern count

Exit 0 = all valid, exit 1 = errors found.
"""

import ast
import importlib.util
import os
import re
import sys

CLAUDE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
BLOCKER_PATH = os.path.join(CLAUDE_DIR, "hooks", "dangerous-command-blocker.py")
LIB_PATH = os.path.join(CLAUDE_DIR, "hooks", "_lib", "git_invocation.py")
LIB_LABEL = "git_invocation"

KNOWN_LISTS = {"CATASTROPHIC", "CRITICAL_PATHS", "SUSPICIOUS", "SAFE_CLEANUP"}


def assignment_targets(node):
    """Yield (target, value) for plain and annotated assignments alike.

    `NAME = [...]` and `NAME: list[tuple[str, str]] = [...]` describe the same
    table. Reading only `ast.Assign` silently skipped the annotated form, which
    reported the list as missing rather than as changed.
    """
    if isinstance(node, ast.Assign):
        for target in node.targets:
            yield target, node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        yield node.target, node.value


def _first_element(elt):
    if isinstance(elt, ast.Tuple) and elt.elts:
        return elt.elts[0]
    return elt


def _is_pattern_node(node):
    is_string = isinstance(node, ast.Constant) and isinstance(node.value, str)
    return is_string or isinstance(node, ast.Name)


def discover_pattern_lists(tree: ast.AST) -> set[str]:
    discovered: set[str] = set()
    for node in ast.walk(tree):
        for target, value in assignment_targets(node):
            if not isinstance(target, ast.Name) or not target.id.isupper():
                continue
            if not isinstance(value, ast.List):
                continue
            if any(_is_pattern_node(_first_element(elt)) for elt in value.elts):
                discovered.add(target.id)
    return discovered


def extract_patterns(source, names=None):
    names = names or {}
    tree = ast.parse(source)
    discovered = discover_pattern_lists(tree)
    patterns: dict[str, list[str]] = {}
    unresolved: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        for target, value in assignment_targets(node):
            if not isinstance(target, ast.Name) or target.id not in discovered:
                continue
            list_name = target.id
            patterns[list_name] = []
            for elt in value.elts:
                first = _first_element(elt)
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    patterns[list_name].append(first.value)
                elif isinstance(first, ast.Name) and first.id in names:
                    patterns[list_name].append(names[first.id])
                elif isinstance(first, ast.Name):
                    unresolved.append((list_name, first.id))

    return patterns, unresolved


def load_lib_constants(lib_path):
    spec = importlib.util.spec_from_file_location("_validated_pattern_lib", lib_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        name: value
        for name, value in vars(module).items()
        if name.isupper() and isinstance(value, str)
    }


def _compile_errors(label, pattern):
    try:
        re.compile(pattern)
    except re.error as exc:
        return [f"  {label}: invalid regex: {pattern!r} -- {exc}"]
    return []


def _duplicate_errors(all_patterns):
    errors = []
    seen = {}
    for list_name, pat in all_patterns:
        if pat in seen:
            errors.append(
                f"  Duplicate pattern in {list_name} (also in {seen[pat]}): {pat!r}"
            )
        else:
            seen[pat] = list_name
    return errors


def validate(blocker_path, lib_path):
    try:
        names = load_lib_constants(lib_path)
    except Exception as exc:
        return [f"  could not load {lib_path}: {type(exc).__name__}: {exc}"], 0

    with open(blocker_path) as f:
        patterns, unresolved = extract_patterns(f.read(), names)

    errors = [
        f"  {list_name}: unresolved pattern name {name}"
        for list_name, name in unresolved
    ]
    missing_required = KNOWN_LISTS - set(patterns)
    if missing_required:
        errors.append(
            f"  Required pattern list(s) missing from blocker: {sorted(missing_required)}"
        )

    all_patterns = []
    for list_name in sorted(patterns):
        pats = patterns[list_name]
        print(f"  {list_name}: {len(pats)} patterns")
        for pat in pats:
            errors.extend(_compile_errors(list_name, pat))
            all_patterns.append((list_name, pat))

    print(f"  {LIB_LABEL} constants: {len(names)} patterns")
    for name, value in sorted(names.items()):
        errors.extend(_compile_errors(f"{LIB_LABEL}.{name}", value))

    errors.extend(_duplicate_errors(all_patterns))
    return errors, len(all_patterns)


def main():
    for path in (BLOCKER_PATH, LIB_PATH):
        if not os.path.exists(path):
            print(f"{path} not found")
            sys.exit(1)

    all_errors, total = validate(BLOCKER_PATH, LIB_PATH)
    print(f"\nTotal patterns: {total}")

    if all_errors:
        print(f"\nFAILED: {len(all_errors)} error(s) found:\n")
        for e in all_errors:
            print(e)
        sys.exit(1)
    print("PASSED: All patterns valid, no duplicates")
    sys.exit(0)


if __name__ == "__main__":
    main()

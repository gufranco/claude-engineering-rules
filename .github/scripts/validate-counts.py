#!/usr/bin/env python3
"""Validate that hardcoded counts across ~/.claude match actual source values.

Derives counts from source files, then scans all markdown and config files
for references to those counts. Reports mismatches so stale references
are caught before they reach the remote.

Exit 0 = all counts match, exit 1 = mismatches found.
"""

import glob
import json
import os
import re
import sys

CLAUDE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def count_files(pattern):
    """Count files matching a glob pattern."""
    return len(glob.glob(os.path.join(CLAUDE_DIR, pattern)))


def count_lines_matching(filepath, pattern):
    """Count lines matching a regex in a file."""
    try:
        with open(os.path.join(CLAUDE_DIR, filepath)) as f:
            return sum(1 for line in f if re.search(pattern, line))
    except FileNotFoundError:
        return 0


def count_index_entries(section):
    """Count entries in a section of rules/index.yml."""
    try:
        with open(os.path.join(CLAUDE_DIR, "rules/index.yml")) as f:
            content = f.read()
        in_section = False
        count = 0
        for line in content.splitlines():
            if line.startswith(f"{section}:"):
                in_section = True
                continue
            if in_section:
                if re.match(r"^[a-z]", line):
                    break
                if re.match(r"^  [a-z]", line) and not line.strip().startswith("path:"):
                    if not line.strip().startswith(
                        "description:"
                    ) and not line.strip().startswith("triggers:"):
                        count += 1
        return count
    except FileNotFoundError:
        return 0


def count_mcp_servers():
    """Count MCP servers in settings.json."""
    try:
        with open(os.path.join(CLAUDE_DIR, "settings.json")) as f:
            data = json.load(f)
        return len(data.get("mcpServers", {}))
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


def count_run_tests():
    """Count run_test calls in test-hooks.sh (excluding function definition)."""
    try:
        with open(os.path.join(CLAUDE_DIR, "tests/test-hooks.sh")) as f:
            content = f.read()
        return len(re.findall(r"^run_test ", content, re.MULTILINE))
    except FileNotFoundError:
        return 0


def derive_counts():
    """Derive all counts from source files."""
    return {
        "rules": count_files("rules/*.md"),
        "always_on_rules": count_index_entries("always_loaded"),
        "standards": count_files("standards/*.md"),
        "skills": count_files("skills/*/SKILL.md"),
        "hooks": count_files("hooks/*.sh") + count_files("hooks/*.py"),
        "checklist_items": count_lines_matching("checklists/checklist.md", r"^- \["),
        "checklist_categories": count_lines_matching(
            "checklists/checklist.md", r"^### \d+"
        ),
        "mcp_servers": count_mcp_servers(),
        "test_cases": count_run_tests(),
        "on_demand_standards": count_index_entries("on_demand"),
    }


def scan_file(filepath, counts):
    """Scan a file, returning (mismatches, labels that matched at least once)."""
    mismatches = []
    matched_labels = set()
    try:
        with open(filepath) as f:
            content = f.read()
    except (FileNotFoundError, UnicodeDecodeError):
        return mismatches, matched_labels

    rel_path = os.path.relpath(filepath, CLAUDE_DIR)

    checks = [
        (
            r"\*\*(\d+)\*\*\s*(?:always-on|universal)\s+rules\b",
            "always_on_rules",
            "always-on rules count in bold",
        ),
        (r"\*\*(\d+)\*\*\s*rules\b", "rules", "rules count in bold"),
        (
            r"(?<!\d[-])(\d+)\s+(?:always-on|universal)\s+rules\b",
            "always_on_rules",
            "always-on rules count",
        ),
        (
            r"\*\*(\d+)\*\*\s*(?:[a-z-]+\s+)?standards\b",
            "standards",
            "standards count in bold",
        ),
        (r"\*\*(\d+)\*\*\s*(?:[a-z-]+\s+)?skills\b", "skills", "skills count in bold"),
        (r"\*\*(\d+)\*\*\s*(?:[a-z-]+\s+)?hooks\b", "hooks", "hooks count in bold"),
        (
            r"\*\*(\d+)\*\*\s*checklist items",
            "checklist_items",
            "checklist items count in bold",
        ),
        (
            r"\*\*(\d+)\*\*\s*categories\b",
            "checklist_categories",
            "categories count in bold",
        ),
        (r"(?<!\d[-])(\d+) on-demand standards", "standards", "standards count"),
        (r"(\d+) checklist items", "checklist_items", "checklist items count"),
        (
            r"(\d+) categories,\s*(\d+) items",
            None,
            "categories and items",
        ),
        (r"(\d+)-item\b", "checklist_items", "N-item reference"),
        (r"(\d+)-category\b", "checklist_categories", "N-category reference"),
        (r"Hook smoke tests \((\d+) cases\)", "test_cases", "test case count"),
        (
            r"These (\d+) standards\b",
            "standards",
            "standards count in prose",
        ),
        (
            r"These (\d+) rules\b",
            "rules",
            "rules count in prose",
        ),
        (r"all (\d+) quality categories", "checklist_categories", "quality categories"),
        (r"(?:all|full) (\d+) categories\b", "checklist_categories", "all categories"),
        (r"(\d+) checklist categories", "checklist_categories", "checklist categories"),
        (
            r"(\d+) categories (?:covering|from|spanning|across)",
            "checklist_categories",
            "categories in context",
        ),
    ]

    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern, count_key, desc in checks:
            for match in re.finditer(pattern, line):
                matched_labels.add(desc)
                if count_key is None:
                    found_cats = int(match.group(1))
                    found_items = int(match.group(2))
                    if found_cats != counts["checklist_categories"]:
                        mismatches.append(
                            f"  {rel_path}:{line_num}: {desc}: "
                            f"found {found_cats} categories, expected {counts['checklist_categories']}"
                        )
                    if found_items != counts["checklist_items"]:
                        mismatches.append(
                            f"  {rel_path}:{line_num}: {desc}: "
                            f"found {found_items} items, expected {counts['checklist_items']}"
                        )
                else:
                    found = int(match.group(1))
                    expected = counts[count_key]
                    if found != expected:
                        mismatches.append(
                            f"  {rel_path}:{line_num}: {desc}: "
                            f"found {found}, expected {expected}"
                        )

    return mismatches, matched_labels


REQUIRED_LABELS = (
    "always-on rules count in bold",
    "standards count in bold",
    "skills count in bold",
    "hooks count in bold",
)


def dead_patterns(matched_labels):
    """Report every required check that matched nothing anywhere.

    A check that never fires cannot fail, so it reports success while
    verifying nothing. That is how a stale number survives a passing run:
    the prose gains a word, the pattern stops matching, and the gate keeps
    printing PASSED.
    """
    return [
        f"  check '{label}' matched nothing in any scanned file. Either the "
        f"prose that carried it changed shape, or the check is dead. A check "
        f"that never fires reports success while verifying nothing."
        for label in REQUIRED_LABELS
        if label not in matched_labels
    ]


def files_to_scan():
    """Every file whose prose may carry a count reference."""
    paths = []
    for pattern in [
        "*.md",
        "rules/*.md",
        "standards/*.md",
        "skills/*/SKILL.md",
        "skills/review/reviewer-prompt.md",
        "checklists/*.md",
    ]:
        paths.extend(glob.glob(os.path.join(CLAUDE_DIR, pattern)))
    return sorted(set(paths))


def main():
    counts = derive_counts()

    print("Derived counts from source:")
    for key, value in sorted(counts.items()):
        print(f"  {key}: {value}")
    print()

    all_mismatches = []
    matched_labels = set()
    for filepath in files_to_scan():
        mismatches, labels = scan_file(filepath, counts)
        all_mismatches.extend(mismatches)
        matched_labels |= labels

    dead = dead_patterns(matched_labels)

    if all_mismatches or dead:
        if all_mismatches:
            print(f"FAILED: {len(all_mismatches)} stale reference(s) found:\n")
            for m in all_mismatches:
                print(m)
            print("\nUpdate these references to match the derived counts above.")
        if dead:
            print(f"\nFAILED: {len(dead)} check(s) matched nothing:\n")
            for d in dead:
                print(d)
            print("\nRestore the prose the check expects, or update the check.")
        sys.exit(1)
    else:
        print("PASSED: All count references match source, and every required")
        print("check matched at least once.")
        sys.exit(0)


if __name__ == "__main__":
    main()

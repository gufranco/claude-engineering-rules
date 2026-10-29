#!/usr/bin/env python3
import glob
import json
import os
import re
import sys

CLAUDE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def count_files(pattern, base_dir=CLAUDE_DIR):
    return len(glob.glob(os.path.join(base_dir, pattern)))


def count_lines_matching(filepath, pattern, base_dir=CLAUDE_DIR):
    try:
        with open(os.path.join(base_dir, filepath), encoding="utf-8") as f:
            return sum(1 for line in f if re.search(pattern, line))
    except FileNotFoundError:
        return 0


def count_index_entries(section, base_dir=CLAUDE_DIR):
    try:
        with open(os.path.join(base_dir, "rules/index.yml"), encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return 0
    in_section = False
    count = 0
    for line in content.splitlines():
        if line.startswith(f"{section}:"):
            in_section = True
        elif in_section and re.match(r"^[a-z]", line):
            break
        elif in_section and re.match(r"^  [a-z]", line):
            count += 1
    return count


def count_mcp_servers(base_dir=CLAUDE_DIR):
    try:
        with open(os.path.join(base_dir, "settings.json"), encoding="utf-8") as f:
            data = json.load(f)
        return len(data.get("mcpServers", {}))
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


def count_run_tests(base_dir=CLAUDE_DIR):
    try:
        with open(
            os.path.join(base_dir, "tests/fixtures/hook-smoke-cases.json"),
            encoding="utf-8",
        ) as f:
            return len(json.load(f))
    except FileNotFoundError:
        return 0


def count_agents(base_dir=CLAUDE_DIR):
    excluded = {"TEMPLATE.md", "_shared-principles.md"}
    paths = glob.glob(os.path.join(base_dir, "agents/*.md"))
    return len([p for p in paths if os.path.basename(p) not in excluded])


def count_lang_rules(base_dir=CLAUDE_DIR):
    paths = glob.glob(os.path.join(base_dir, "rules/lang/*.md"))
    return len([p for p in paths if os.path.basename(p) != "README.md"])


def derive_counts(base_dir=CLAUDE_DIR):
    checklist = "checklists/checklist.md"
    return {
        "rules": count_files("rules/*.md", base_dir),
        "lang_rules": count_lang_rules(base_dir),
        "agents": count_agents(base_dir),
        "always_on_rules": count_index_entries("always_loaded", base_dir),
        "standards": count_files("standards/*.md", base_dir),
        "skills": count_files("skills/*/SKILL.md", base_dir),
        "hooks": count_files("hooks/*.sh", base_dir)
        + count_files("hooks/*.py", base_dir),
        "checklist_items": count_lines_matching(checklist, r"^- \[", base_dir),
        "checklist_categories": count_lines_matching(checklist, r"^### \d+", base_dir),
        "mcp_servers": count_mcp_servers(base_dir),
        "test_cases": count_run_tests(base_dir),
        "on_demand_standards": count_index_entries("on_demand", base_dir),
    }


COUNT_CHECKS = [
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
    (r"^(\d+) (?:[a-z-]+\s+)?skills\b", "skills", "skills count leading a line"),
    (r"^(\d+) (?:[a-z-]+\s+)?hooks\b", "hooks", "hooks count leading a line"),
    (r"(?<=\s)(\d+) skills in\b", "skills", "skills count in prose"),
    (r"(?<=\s)(\d+) hooks in\b", "hooks", "hooks count in prose"),
    (r"^(\d+) standards in\b", "standards", "standards count leading a line"),
    (r"^(\d+) rules in \[", "rules", "rules count leading a line"),
    (r"plus (\d+) in \[`rules/lang/`\]", "lang_rules", "language rules count"),
    (r"Plus (\d+) language-specific files", "lang_rules", "language files count"),
    (r"(\d+) language-specific cores", "lang_rules", "language cores count"),
    (r"(\d+) specialized subagents", "agents", "agents count in prose"),
    (r"\*\*(\d+)\*\*\s*custom agents", "agents", "agents count in bold"),
    (r"^(\d+) MCP servers\b", "mcp_servers", "MCP servers count"),
    (r"The (\d+) standards total", "standards", "standards total in prose"),
    (r"(\d+) short rule cores", "rules", "rule cores count"),
    (r"(?<=  )(\d+) slash-command skills", "skills", "skills count in tree"),
    (r"(?<=  )(\d+) runtime hooks", "hooks", "hooks count in tree"),
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


def _pair_mismatches(prefix, match, counts):
    found_cats = int(match.group(1))
    found_items = int(match.group(2))
    mismatches = []
    if found_cats != counts["checklist_categories"]:
        mismatches.append(
            f"{prefix}found {found_cats} categories, expected {counts['checklist_categories']}"
        )
    if found_items != counts["checklist_items"]:
        mismatches.append(
            f"{prefix}found {found_items} items, expected {counts['checklist_items']}"
        )
    return mismatches


def _match_mismatches(prefix, count_key, match, counts):
    if count_key is None:
        return _pair_mismatches(prefix, match, counts)
    found = int(match.group(1))
    expected = counts[count_key]
    if found == expected:
        return []
    return [f"{prefix}found {found}, expected {expected}"]


def scan_file(filepath, counts, base_dir=CLAUDE_DIR):
    mismatches = []
    matched_labels = set()
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as error:
        return [f"  {filepath}: unreadable: {error}"], matched_labels
    rel_path = os.path.relpath(filepath, base_dir)
    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern, count_key, desc in COUNT_CHECKS:
            prefix = f"  {rel_path}:{line_num}: {desc}: "
            for match in re.finditer(pattern, line):
                matched_labels.add(desc)
                mismatches.extend(_match_mismatches(prefix, count_key, match, counts))
    return mismatches, matched_labels


REQUIRED_LABELS = (
    "always-on rules count in bold",
    "standards count in bold",
    "skills count in bold",
    "hooks count in bold",
)


def dead_patterns(matched_labels):
    return [
        f"  check '{label}' matched nothing in any scanned file. Either the "
        f"prose that carried it changed shape, or the check is dead. A check "
        f"that never fires reports success while verifying nothing."
        for label in REQUIRED_LABELS
        if label not in matched_labels
    ]


def files_to_scan(base_dir=CLAUDE_DIR):
    paths = []
    for pattern in [
        "*.md",
        "rules/*.md",
        "standards/*.md",
        "skills/*/SKILL.md",
        "skills/review/reviewer-prompt.md",
        "checklists/*.md",
    ]:
        paths.extend(glob.glob(os.path.join(base_dir, pattern)))
    return sorted(set(paths))


def _print_counts(counts):
    print("Derived counts from source:")
    for key, value in sorted(counts.items()):
        print(f"  {key}: {value}")
    print()


def _print_failures(all_mismatches, dead):
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


def main(base_dir=CLAUDE_DIR):
    counts = derive_counts(base_dir)
    _print_counts(counts)
    all_mismatches = []
    matched_labels = set()
    for filepath in files_to_scan(base_dir):
        mismatches, labels = scan_file(filepath, counts, base_dir)
        all_mismatches.extend(mismatches)
        matched_labels |= labels
    dead = dead_patterns(matched_labels)
    if all_mismatches or dead:
        _print_failures(all_mismatches, dead)
        return 1
    print("PASSED: All count references match source, and every required")
    print("check matched at least once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

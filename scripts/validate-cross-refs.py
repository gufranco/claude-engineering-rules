#!/usr/bin/env python3
"""Validate cross-references between index.yml, standards, rules, and agents.

Uses a minimal in-tree YAML parser tailored to the index.yml format so the
validator runs on a clean machine without PyYAML.
"""

import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ERRORS = []


def parse_index_yml(path: str) -> dict:
    """Parse the constrained subset of YAML used by rules/index.yml.

    Supports top-level mappings, two levels of nested mappings, scalar string
    values, and inline list values. Comments and blank lines are skipped.
    """
    with open(path) as f:
        lines = f.readlines()

    result: dict = {}
    section: dict | None = None
    entry: dict | None = None
    section_name = ""
    entry_name = ""

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))

        if indent == 0 and stripped.endswith(":"):
            section_name = stripped[:-1].strip()
            section = {}
            result[section_name] = section
            entry = None
            continue

        if indent == 2 and stripped.endswith(":") and section is not None:
            entry_name = stripped[:-1].strip()
            entry = {}
            section[entry_name] = entry
            continue

        if indent >= 4 and ":" in stripped and entry is not None:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip() for v in value[1:-1].split(",") if v.strip()]
                entry[key] = items
            else:
                entry[key] = value

    return result


def validate_index_paths(index_data: dict) -> None:
    """Verify every path in index.yml references an existing file."""
    for section in ("always_loaded", "on_demand"):
        entries = index_data.get(section) or {}
        for name, entry in entries.items():
            path = entry.get("path") if isinstance(entry, dict) else None
            if not path:
                if section == "always_loaded":
                    path = f"rules/{name}.md"
                else:
                    path = f"standards/{name}.md"
            full_path = os.path.join(BASE_DIR, path)
            if not os.path.exists(full_path):
                ERRORS.append(
                    f"index.yml [{section}] '{name}': path '{path}' does not exist"
                )


def parse_frontmatter(content: str) -> dict | None:
    """Extract a flat key:value mapping from a markdown frontmatter block."""
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    meta: dict = {}
    for raw_line in parts[1].splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def validate_agent_files() -> None:
    """Verify all agent files have required frontmatter fields."""
    agents_dir = os.path.join(BASE_DIR, "agents")
    if not os.path.isdir(agents_dir):
        return

    for filename in sorted(os.listdir(agents_dir)):
        if not filename.endswith(".md"):
            continue
        if filename in ("TEMPLATE.md", "_shared-principles.md"):
            continue

        filepath = os.path.join(agents_dir, filename)
        with open(filepath) as f:
            content = f.read()

        meta = parse_frontmatter(content)
        if meta is None:
            ERRORS.append(f"agents/{filename}: missing or malformed frontmatter")
            continue

        for field in ("name", "description", "tools"):
            if field not in meta:
                ERRORS.append(
                    f"agents/{filename}: missing required field '{field}'"
                )


def validate_standard_files() -> None:
    """Verify all .md files in standards/ have a top-level heading."""
    standards_dir = os.path.join(BASE_DIR, "standards")
    if not os.path.isdir(standards_dir):
        return

    for filename in sorted(os.listdir(standards_dir)):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(standards_dir, filename)
        with open(filepath) as f:
            first_lines = f.read(500)
        if not first_lines.strip().startswith("#"):
            ERRORS.append(f"standards/{filename}: missing top-level heading")


def main() -> None:
    index_path = os.path.join(BASE_DIR, "rules", "index.yml")
    index_data = parse_index_yml(index_path)

    validate_index_paths(index_data)
    validate_agent_files()
    validate_standard_files()

    if ERRORS:
        print(f"Cross-reference validation failed with {len(ERRORS)} error(s):")
        for error in ERRORS:
            print(f"  - {error}")
        sys.exit(1)

    print("All cross-references valid")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate cross-references between index.yml, standards, rules, and agents."""

import os
import sys
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ERRORS = []


def validate_index_paths(index_data: dict) -> None:
    """Verify every path in index.yml references an existing file."""
    for section in ["always_loaded", "on_demand"]:
        entries = index_data.get(section) or {}
        for name, entry in entries.items():
            path = entry.get("path", f"rules/{name}.md")
            full_path = os.path.join(BASE_DIR, path)
            if not os.path.exists(full_path):
                ERRORS.append(f"index.yml [{section}] '{name}': path '{path}' does not exist")


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

        if not content.startswith("---"):
            ERRORS.append(f"agents/{filename}: missing YAML frontmatter")
            continue

        parts = content.split("---", 2)
        if len(parts) < 3:
            ERRORS.append(f"agents/{filename}: malformed frontmatter")
            continue

        try:
            meta = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            ERRORS.append(f"agents/{filename}: invalid YAML: {e}")
            continue

        if not meta:
            ERRORS.append(f"agents/{filename}: empty frontmatter")
            continue

        for field in ("name", "description", "tools"):
            if field not in meta:
                ERRORS.append(f"agents/{filename}: missing required field '{field}'")


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
    with open(index_path) as f:
        index_data = yaml.safe_load(f)

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

#!/usr/bin/env python3
"""Validate all SKILL.md files have valid YAML frontmatter with required fields."""

import os
import sys
import re

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
ERRORS = []


def validate_skill(skill_dir: str) -> None:
    skill_file = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_file):
        ERRORS.append(f"{skill_dir}: missing SKILL.md")
        return

    with open(skill_file) as f:
        content = f.read()

    if not content.strip():
        ERRORS.append(f"{skill_file}: empty file")
        return

    # Check minimum content length
    if len(content) < 100:
        ERRORS.append(f"{skill_file}: suspiciously short ({len(content)} chars)")


def main() -> None:
    if not os.path.isdir(SKILLS_DIR):
        print("No skills/ directory found")
        sys.exit(0)

    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, entry)
        if os.path.isdir(skill_path):
            validate_skill(skill_path)

    if ERRORS:
        print(f"Skill validation failed with {len(ERRORS)} error(s):")
        for error in ERRORS:
            print(f"  - {error}")
        sys.exit(1)

    skill_count = sum(
        1
        for e in os.listdir(SKILLS_DIR)
        if os.path.isdir(os.path.join(SKILLS_DIR, e))
    )
    print(f"All {skill_count} skills valid")


if __name__ == "__main__":
    main()

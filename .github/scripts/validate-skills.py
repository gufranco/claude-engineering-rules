#!/usr/bin/env python3
import os
import re
import sys

CLAUDE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
SKILLS_DIR = os.path.join(CLAUDE_DIR, "skills")

REQUIRED_FIELDS = {"name", "description"}

HARNESS_MANAGED_GITIGNORED_DIRS = frozenset({"synced"})

SENSITIVE_TERMS = re.compile(
    r"\b(git push|gh pr merge|git merge|git reset --hard|git rebase|"
    r"force.?push|force.?with.?lease|deploy|rollback|destroy|drop\s+(table|database)|"
    r"revoke|supersede|rm\s+-rf|terraform apply|kubectl apply|kubectl delete)\b",
    re.IGNORECASE,
)


def parse_frontmatter(content: str):
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return None, ""
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        kv = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if kv:
            fields[kv.group(1)] = kv.group(2).strip()
    body = content[match.end() :]
    return fields, body


def validate_skill(skill_dir: str) -> list[str]:
    errors: list[str] = []
    rel = os.path.relpath(skill_dir, CLAUDE_DIR)
    skill_file = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_file):
        return [f"  {rel}: missing SKILL.md"]

    with open(skill_file) as f:
        content = f.read()

    if not content.strip():
        return [f"  {rel}/SKILL.md: empty"]

    if len(content) < 100:
        errors.append(f"  {rel}/SKILL.md: suspiciously short ({len(content)} chars)")

    fields, body = parse_frontmatter(content)
    if fields is None:
        errors.append(f"  {rel}/SKILL.md: missing YAML frontmatter")
        return errors

    for field in REQUIRED_FIELDS:
        if field not in fields:
            errors.append(f"  {rel}/SKILL.md: missing required field '{field}'")

    sensitive_match = SENSITIVE_TERMS.search(body)
    declared = fields.get("sensitive", "false").lower() in {"true", "yes", "1"}
    if sensitive_match and not declared:
        line_num = body[: sensitive_match.start()].count("\n") + 1
        absolute_line = content[: content.find(body)].count("\n") + line_num
        errors.append(
            f"  {rel}/SKILL.md:{absolute_line}: body mentions irreversible action "
            f"'{sensitive_match.group(0)}' but frontmatter is missing 'sensitive: true'"
        )

    return errors


def skill_dirs(skills_dir: str) -> list[str]:
    return [
        os.path.join(skills_dir, entry)
        for entry in sorted(os.listdir(skills_dir))
        if os.path.isdir(os.path.join(skills_dir, entry))
        and not entry.startswith(".")
        and entry not in HARNESS_MANAGED_GITIGNORED_DIRS
    ]


def main() -> None:
    if not os.path.isdir(SKILLS_DIR):
        print("No skills/ directory found")
        sys.exit(0)

    found = skill_dirs(SKILLS_DIR)
    all_errors = [error for path in found for error in validate_skill(path)]
    skill_count = len(found)

    print(f"Validated {skill_count} skills")
    if all_errors:
        print(f"\nFAILED: {len(all_errors)} error(s):\n")
        for e in all_errors:
            print(e)
        sys.exit(1)
    print("PASSED: all skills valid")


if __name__ == "__main__":
    main()

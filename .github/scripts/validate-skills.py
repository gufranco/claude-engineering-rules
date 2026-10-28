#!/usr/bin/env python3
import os
import re
import sys

CLAUDE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

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


def _sensitive_errors(
    rel: str, content: str, fields: dict[str, str], body: str
) -> list[str]:
    sensitive_match = SENSITIVE_TERMS.search(body)
    declared = fields.get("sensitive", "false").lower() in {"true", "yes", "1"}
    if not sensitive_match or declared:
        return []
    line_num = body[: sensitive_match.start()].count("\n") + 1
    absolute_line = content[: content.find(body)].count("\n") + line_num
    return [
        f"  {rel}/SKILL.md:{absolute_line}: body mentions irreversible action "
        f"'{sensitive_match.group(0)}' but frontmatter is missing 'sensitive: true'"
    ]


def validate_skill(skill_dir: str, claude_dir: str = CLAUDE_DIR) -> list[str]:
    rel = os.path.relpath(skill_dir, claude_dir)
    skill_file = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_file):
        return [f"  {rel}: missing SKILL.md"]
    with open(skill_file, encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return [f"  {rel}/SKILL.md: empty"]
    errors: list[str] = []
    if len(content) < 100:
        errors.append(f"  {rel}/SKILL.md: suspiciously short ({len(content)} chars)")
    fields, body = parse_frontmatter(content)
    if fields is None:
        return [*errors, f"  {rel}/SKILL.md: missing YAML frontmatter"]
    missing = [
        f"  {rel}/SKILL.md: missing required field '{field}'"
        for field in REQUIRED_FIELDS
        if field not in fields
    ]
    return [*errors, *missing, *_sensitive_errors(rel, content, fields, body)]


def skill_dirs(skills_dir: str) -> list[str]:
    return [
        os.path.join(skills_dir, entry)
        for entry in sorted(os.listdir(skills_dir))
        if os.path.isdir(os.path.join(skills_dir, entry))
        and not entry.startswith(".")
        and entry not in HARNESS_MANAGED_GITIGNORED_DIRS
    ]


def main(claude_dir: str = CLAUDE_DIR) -> int:
    skills_dir = os.path.join(claude_dir, "skills")
    if not os.path.isdir(skills_dir):
        print("No skills/ directory found")
        return 0

    found = skill_dirs(skills_dir)
    all_errors = [error for path in found for error in validate_skill(path, claude_dir)]

    print(f"Validated {len(found)} skills")
    if all_errors:
        print(f"\nFAILED: {len(all_errors)} error(s):\n")
        for e in all_errors:
            print(e)
        return 1
    print("PASSED: all skills valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())

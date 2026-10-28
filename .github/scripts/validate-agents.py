#!/usr/bin/env python3
import glob
import os
import re
import sys

CLAUDE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
VALID_MODELS = {"haiku", "sonnet", "opus"}
REQUIRED_FIELDS = {"name", "description", "tools", "model"}


def parse_frontmatter(content):
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return None

    fields = {}
    current_key = None
    list_values = []

    for line in match.group(1).splitlines():
        list_match = re.match(r"^\s+-\s+(.+)", line)
        if list_match and current_key:
            list_values.append(list_match.group(1).strip())
            fields[current_key] = list_values
            continue

        kv_match = re.match(r"^(\w+):\s*(.*)", line)
        if kv_match:
            current_key = kv_match.group(1)
            value = kv_match.group(2).strip()
            list_values = []
            if value:
                fields[current_key] = value

    return fields


def _field_errors(rel_path: str, fields: dict[str, str | list[str]]) -> list[str]:
    errors = [
        f"  {rel_path}: missing required field '{field}'"
        for field in REQUIRED_FIELDS
        if field not in fields
    ]
    model = fields.get("model", "")
    if model and model not in VALID_MODELS:
        errors.append(
            f"  {rel_path}: invalid model '{model}', must be one of: {', '.join(sorted(VALID_MODELS))}"
        )
    tools = fields.get("tools")
    if tools is not None and not isinstance(tools, list):
        errors.append(f"  {rel_path}: 'tools' must be a list")
    elif isinstance(tools, list) and len(tools) == 0:
        errors.append(f"  {rel_path}: 'tools' list is empty")
    return errors


def _body_errors(rel_path: str, content: str) -> list[str]:
    body = content.split("---", 2)[-1]
    body_offset = content.find(body)
    body_line_start = content[:body_offset].count("\n") + 1
    errors: list[str] = []
    if "Do not spawn subagents" not in body:
        errors.append(
            f"  {rel_path}:{body_line_start}: body missing 'Do not spawn subagents' constraint"
        )
    if not re.search(r"do not push", body, re.IGNORECASE):
        errors.append(
            f"  {rel_path}:{body_line_start}: body missing 'Do not push' prohibition "
            f"(orchestrator pushes; agents must not)"
        )
    return errors


def validate_agent(filepath, claude_dir=CLAUDE_DIR):
    rel_path = os.path.relpath(filepath, claude_dir)
    with open(filepath) as f:
        content = f.read()
    fields = parse_frontmatter(content)
    if fields is None:
        return [f"  {rel_path}: missing YAML frontmatter (--- delimiters)"]
    return [*_field_errors(rel_path, fields), *_body_errors(rel_path, content)]


SKIP_FILES = frozenset({"TEMPLATE.md", "_shared-principles.md"})


def main(claude_dir=CLAUDE_DIR):
    agent_files = [
        path
        for path in sorted(glob.glob(os.path.join(claude_dir, "agents", "*.md")))
        if os.path.basename(path) not in SKIP_FILES
    ]
    if not agent_files:
        print("No agent files found in agents/")
        return 0
    all_errors = [
        error for path in agent_files for error in validate_agent(path, claude_dir)
    ]
    print(f"Validated {len(agent_files)} agent definitions")
    if all_errors:
        print(f"\nFAILED: {len(all_errors)} error(s) found:\n")
        for error in all_errors:
            print(error)
        return 1
    print("PASSED: All agent definitions valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())

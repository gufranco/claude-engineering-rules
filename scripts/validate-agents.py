#!/usr/bin/env python3
"""Validate agent definition files in agents/*.md.

Checks:
  - YAML frontmatter exists (delimited by ---)
  - Required fields: name, description, tools, model
  - model is one of: haiku, sonnet, opus
  - tools is a non-empty list
  - Body contains "Do not spawn subagents" constraint

Skips TEMPLATE.md (reference template, not a real agent).

Exit 0 = all valid, exit 1 = errors found.
"""

import glob
import os
import re
import sys

CLAUDE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(CLAUDE_DIR, "agents")
VALID_MODELS = {"haiku", "sonnet", "opus"}
REQUIRED_FIELDS = {"name", "description", "tools", "model"}


def parse_frontmatter(content):
    """Extract YAML frontmatter as a dict of key-value pairs."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return None

    fields = {}
    current_key = None
    list_values = []

    for line in match.group(1).splitlines():
        # List item under a key
        list_match = re.match(r"^\s+-\s+(.+)", line)
        if list_match and current_key:
            list_values.append(list_match.group(1).strip())
            fields[current_key] = list_values
            continue

        # Key: value pair
        kv_match = re.match(r"^(\w+):\s*(.*)", line)
        if kv_match:
            current_key = kv_match.group(1)
            value = kv_match.group(2).strip()
            if value:
                fields[current_key] = value
                list_values = []
            else:
                list_values = []
            continue

    return fields


def validate_agent(filepath):
    """Validate a single agent file. Returns list of error strings."""
    errors = []
    rel_path = os.path.relpath(filepath, CLAUDE_DIR)

    with open(filepath) as f:
        content = f.read()

    # Check frontmatter exists
    fields = parse_frontmatter(content)
    if fields is None:
        errors.append(f"  {rel_path}: missing YAML frontmatter (--- delimiters)")
        return errors

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in fields:
            errors.append(f"  {rel_path}: missing required field '{field}'")

    # Check model value
    model = fields.get("model", "")
    if model and model not in VALID_MODELS:
        errors.append(
            f"  {rel_path}: invalid model '{model}', must be one of: {', '.join(sorted(VALID_MODELS))}"
        )

    # Check tools is a non-empty list
    tools = fields.get("tools")
    if tools is not None and not isinstance(tools, list):
        errors.append(f"  {rel_path}: 'tools' must be a list")
    elif isinstance(tools, list) and len(tools) == 0:
        errors.append(f"  {rel_path}: 'tools' list is empty")

    # Check body contains cascade prevention and push prohibition.
    # Use file:line citations so agents can be audited quickly.
    body = content.split("---", 2)[-1] if content.count("---") >= 2 else ""
    body_offset = content.find(body) if body else 0
    body_line_start = content[:body_offset].count("\n") + 1

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


def main():
    agent_files = sorted(glob.glob(os.path.join(AGENTS_DIR, "*.md")))

    if not agent_files:
        print("No agent files found in agents/")
        sys.exit(0)

    # Skip TEMPLATE.md
    skip_files = {"TEMPLATE.md", "_shared-principles.md"}
    agent_files = [f for f in agent_files if os.path.basename(f) not in skip_files]

    all_errors = []
    for filepath in agent_files:
        errors = validate_agent(filepath)
        all_errors.extend(errors)

    print(f"Validated {len(agent_files)} agent definitions")

    if all_errors:
        print(f"\nFAILED: {len(all_errors)} error(s) found:\n")
        for e in all_errors:
            print(e)
        sys.exit(1)
    else:
        print("PASSED: All agent definitions valid")
        sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate settings.json structure and references.

Checks:
  - Valid JSON
  - All deny entries match pattern: (Read|Write|Edit)(<glob>)
  - No duplicate deny entries
  - All hook commands reference scripts that exist on disk
  - All hook matchers are known tool names

Exit 0 = all valid, exit 1 = errors found.
"""

import json
import os
import re
import sys

CLAUDE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(CLAUDE_DIR, "settings.json")

DENY_PATTERN = re.compile(r"^(Read|Write|Edit)\(.+\)$")

KNOWN_MATCHERS = {
    "",  # empty matcher matches all tools
    "Bash",
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "Glob",
    "Grep",
    "WebFetch",
    "WebSearch",
    "Agent",
    "NotebookEdit",
    "Skill",
}


def validate_deny_rules(data):
    """Validate permissions deny rules."""
    errors = []
    deny = data.get("permissions", {}).get("deny", [])

    seen = set()
    for entry in deny:
        if not DENY_PATTERN.match(entry):
            errors.append(f"  Invalid deny pattern: {entry}")

        if entry in seen:
            errors.append(f"  Duplicate deny entry: {entry}")
        seen.add(entry)

    return errors


def validate_hooks(data):
    """Validate hook configurations."""
    errors = []
    hooks = data.get("hooks", {})

    for phase in ("PreToolUse", "PostToolUse", "Stop", "Notification"):
        for hook_group in hooks.get(phase, []):
            matcher = hook_group.get("matcher", "")
            if matcher not in KNOWN_MATCHERS:
                errors.append(
                    f"  Unknown hook matcher '{matcher}' in {phase}"
                )

            for hook in hook_group.get("hooks", []):
                command = hook.get("command", "")
                if not command:
                    continue

                # Extract script path from command
                # Commands look like: "python3 ~/.claude/hooks/foo.py" or "bash ~/.claude/hooks/bar.sh"
                # In CI, ~/.claude/ is the repo root, not the user's home
                parts = command.split()
                for part in parts:
                    if "~/.claude/" in part:
                        relative = part.replace("~/.claude/", "")
                        resolved = os.path.join(CLAUDE_DIR, relative)
                        if not os.path.exists(resolved):
                            errors.append(
                                f"  Hook script not found: {part} (resolved to {relative}) in {phase}"
                            )
                        break

    return errors


def main():
    if not os.path.exists(SETTINGS_PATH):
        print("settings.json not found")
        sys.exit(1)

    with open(SETTINGS_PATH) as f:
        data = json.load(f)

    all_errors = []
    all_errors.extend(validate_deny_rules(data))
    all_errors.extend(validate_hooks(data))

    deny_count = len(data.get("permissions", {}).get("deny", []))
    hook_count = sum(
        len(hg.get("hooks", []))
        for phase in ("PreToolUse", "PostToolUse", "Stop", "Notification")
        for hg in data.get("hooks", {}).get(phase, [])
    )

    print(f"Validated settings.json: {deny_count} deny rules, {hook_count} hook commands")

    if all_errors:
        print(f"\nFAILED: {len(all_errors)} error(s) found:\n")
        for e in all_errors:
            print(e)
        sys.exit(1)
    else:
        print("PASSED: settings.json valid")
        sys.exit(0)


if __name__ == "__main__":
    main()

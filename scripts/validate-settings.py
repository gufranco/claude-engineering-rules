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


KNOWN_HOOK_PHASES = {
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "Notification",
    "UserPromptSubmit",
    "SessionStart",
    "PreCompact",
    "PostCompact",
    "PostToolUseFailure",
}


def validate_mcpservers(data):
    """Validate mcpServers entries have required fields."""
    errors = []
    servers = data.get("mcpServers", {})
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            errors.append(f"  mcpServers.{name}: must be an object")
            continue
        has_command = "command" in cfg
        has_url = "url" in cfg
        if not has_command and not has_url:
            errors.append(
                f"  mcpServers.{name}: must have either 'command' or 'url'"
            )
        if has_command and not isinstance(cfg.get("args", []), list):
            errors.append(
                f"  mcpServers.{name}: 'args' must be a list when 'command' is set"
            )
    return errors


def validate_hooks(data):
    """Validate hook configurations."""
    errors = []
    hooks = data.get("hooks", {})

    for phase in KNOWN_HOOK_PHASES:
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
    all_errors.extend(validate_mcpservers(data))

    deny_count = len(data.get("permissions", {}).get("deny", []))
    hook_count = sum(
        len(hg.get("hooks", []))
        for phase in KNOWN_HOOK_PHASES
        for hg in data.get("hooks", {}).get(phase, [])
    )
    mcp_count = len(data.get("mcpServers", {}))

    print(f"Validated settings.json: {deny_count} deny rules, {hook_count} hook commands, {mcp_count} MCP servers")

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

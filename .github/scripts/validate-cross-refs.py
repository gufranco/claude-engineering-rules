#!/usr/bin/env python3
import glob
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ERRORS = []


def parse_index_yml(path: str) -> dict:
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
                ERRORS.append(f"agents/{filename}: missing required field '{field}'")


def validate_standard_files() -> None:
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


HOOK_CITATION = re.compile(
    r"~/\.claude/((?:rules|standards|skills|checklists|agents)/[A-Za-z0-9_./-]+\.md)"
)
SKILL_REFERENCE = re.compile(r"`/([a-z][a-z0-9-]*)(?=[ `])")
SKILL_REFERENCE_GLOBS = (
    "skills/*/SKILL.md",
    "agents/*.md",
    "rules/*.md",
    "rules/lang/*.md",
    "CLAUDE.md",
)
CLAUDE_CODE_COMMANDS = frozenset(
    {
        "add-dir",
        "agents",
        "artifacts",
        "btw",
        "bug",
        "clear",
        "code-review",
        "compact",
        "config",
        "context",
        "cost",
        "doctor",
        "export",
        "fast",
        "fewer-permission-prompts",
        "help",
        "hooks",
        "init",
        "install-github-app",
        "keybindings-help",
        "login",
        "logout",
        "loop",
        "mcp",
        "memory",
        "model",
        "output-style",
        "permissions",
        "plugin",
        "release-notes",
        "resume",
        "rewind",
        "run",
        "schedule",
        "security-review",
        "simplify",
        "status",
        "statusline",
        "terminal-setup",
        "todos",
        "update-config",
        "upgrade",
        "usage",
        "usage-credits",
        "vim",
        "workflows",
    }
)


def find_missing_hook_citations(base_dir: str) -> list[str]:
    errors: list[str] = []
    for hook in sorted(glob.glob(os.path.join(base_dir, "hooks", "*.py"))):
        with open(hook, encoding="utf-8") as handle:
            cited = sorted(set(HOOK_CITATION.findall(handle.read())))
        relative_hook = os.path.relpath(hook, base_dir)
        errors.extend(
            f"{relative_hook} cites ~/.claude/{target}, which does not exist"
            for target in cited
            if not os.path.exists(os.path.join(base_dir, target))
        )
    return errors


def skill_names(base_dir: str) -> frozenset[str]:
    return frozenset(
        os.path.basename(os.path.dirname(path))
        for path in glob.glob(os.path.join(base_dir, "skills", "*", "SKILL.md"))
    )


def find_unknown_skill_references(base_dir: str, commands: frozenset[str]) -> list[str]:
    known = skill_names(base_dir) | commands
    errors: list[str] = []
    for pattern in SKILL_REFERENCE_GLOBS:
        for path in sorted(glob.glob(os.path.join(base_dir, pattern))):
            relative = os.path.relpath(path, base_dir)
            with open(path, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            errors.extend(
                f"{relative}:{number} references /{name}, which is neither a skill nor a built-in command"
                for number, line in enumerate(lines, start=1)
                for name in SKILL_REFERENCE.findall(line)
                if name not in known
            )
    return errors


def main() -> None:
    index_path = os.path.join(BASE_DIR, "rules", "index.yml")
    index_data = parse_index_yml(index_path)

    validate_index_paths(index_data)
    validate_agent_files()
    validate_standard_files()
    ERRORS.extend(find_missing_hook_citations(BASE_DIR))
    ERRORS.extend(find_unknown_skill_references(BASE_DIR, CLAUDE_CODE_COMMANDS))

    if ERRORS:
        print(f"Cross-reference validation failed with {len(ERRORS)} error(s):")
        for error in ERRORS:
            print(f"  - {error}")
        sys.exit(1)

    print("All cross-references valid")


if __name__ == "__main__":
    main()

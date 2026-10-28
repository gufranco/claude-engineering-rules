#!/usr/bin/env python3
import glob
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _parse_index_value(value: str) -> str | list[str]:
    if value.startswith("[") and value.endswith("]"):
        return [v.strip() for v in value[1:-1].split(",") if v.strip()]
    return value


def parse_index_yml(path: str) -> dict:
    with open(path) as f:
        lines = f.readlines()
    result: dict = {}
    section: dict | None = None
    entry: dict | None = None
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            section = {}
            result[stripped[:-1].strip()] = section
            entry = None
        elif indent == 2 and stripped.endswith(":") and section is not None:
            entry = {}
            section[stripped[:-1].strip()] = entry
        elif indent >= 4 and ":" in stripped and entry is not None:
            key, _, value = stripped.partition(":")
            entry[key.strip()] = _parse_index_value(value.strip())
    return result


DEFAULT_DIRS = {"always_loaded": "rules", "on_demand": "standards"}


def _index_path(section: str, name: str, entry: object) -> str:
    path = entry.get("path") if isinstance(entry, dict) else None
    return str(path) if path else f"{DEFAULT_DIRS[section]}/{name}.md"


def validate_index_paths(index_data: dict, base_dir: str) -> list[str]:
    return [
        f"index.yml [{section}] '{name}': path '{path}' does not exist"
        for section in DEFAULT_DIRS
        for name, entry in (index_data.get(section) or {}).items()
        if not os.path.exists(
            os.path.join(base_dir, path := _index_path(section, name, entry))
        )
    ]


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


AGENT_SKIPPED = frozenset({"TEMPLATE.md", "_shared-principles.md"})
AGENT_FIELDS = ("name", "description", "tools")


def _agent_errors(filename: str, content: str) -> list[str]:
    meta = parse_frontmatter(content)
    if meta is None:
        return [f"agents/{filename}: missing or malformed frontmatter"]
    return [
        f"agents/{filename}: missing required field '{field}'"
        for field in AGENT_FIELDS
        if field not in meta
    ]


def validate_agent_files(base_dir: str) -> list[str]:
    paths = sorted(glob.glob(os.path.join(base_dir, "agents", "*.md")))
    return [
        error
        for path in paths
        if os.path.basename(path) not in AGENT_SKIPPED
        for error in _agent_errors(os.path.basename(path), _read(path))
    ]


def validate_standard_files(base_dir: str) -> list[str]:
    paths = sorted(glob.glob(os.path.join(base_dir, "standards", "*.md")))
    return [
        f"standards/{os.path.basename(path)}: missing top-level heading"
        for path in paths
        if not _read(path)[:500].strip().startswith("#")
    ]


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


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


def collect_errors(base_dir: str) -> list[str]:
    index_data = parse_index_yml(os.path.join(base_dir, "rules", "index.yml"))
    return [
        *validate_index_paths(index_data, base_dir),
        *validate_agent_files(base_dir),
        *validate_standard_files(base_dir),
        *find_missing_hook_citations(base_dir),
        *find_unknown_skill_references(base_dir, CLAUDE_CODE_COMMANDS),
    ]


def main(base_dir: str = BASE_DIR) -> int:
    errors = collect_errors(base_dir)
    if errors:
        print(f"Cross-reference validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("All cross-references valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())

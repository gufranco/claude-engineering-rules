#!/usr/bin/env python3
"""Detect registry drift: an artifact on disk that nothing points at.

The existing validators walk from a registry to disk. `validate-cross-refs.py`
confirms every path named in `rules/index.yml` exists, and `validate-counts.py`
confirms the numbers written in prose match what is on disk. Both are
one-directional, so a file added without being registered passes every check:
the index still resolves, and the counts only compare totals somebody wrote
down.

This validator walks the other way, starting from the files that exist and
asking what fails to reference them. That is the direction real drift arrives
from: a new rule that never reaches a session because the index does not list
it, a skill nobody can discover from the README, or a stray non-hook file in
the hooks directory where a smoke test will try to execute it.

Exit code 0 when clean, 1 with a per-finding report otherwise.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

AGENT_NON_AGENTS = {"TEMPLATE", "_shared-principles", "README"}

TEST_SHAPED = re.compile(r"(^test_|_test\.py$|\.test\.py$|^conftest\.py$)")


def load_index() -> dict:
    """Reuse the in-tree index parser so this validator needs no PyYAML."""
    path = ROOT / ".github" / "scripts" / "validate-cross-refs.py"
    spec = importlib.util.spec_from_file_location("_cross_refs", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the index parser from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_index_yml(str(ROOT / "rules" / "index.yml"))


def check_rules_registered(index: dict, findings: list[str]) -> None:
    registered = set(index.get("always_loaded", {})) | set(index.get("on_demand", {}))
    on_disk = {p.stem for p in (ROOT / "rules").glob("*.md")}
    for name in sorted(on_disk - registered):
        findings.append(
            f"rules/{name}.md exists but has no entry in rules/index.yml. "
            f"An unregistered rule never loads, so it silently does nothing."
        )


def check_standards_registered(index: dict, findings: list[str]) -> None:
    registered = set(index.get("on_demand", {}))
    on_disk = {p.stem for p in (ROOT / "standards").glob("*.md")}
    for name in sorted(on_disk - registered):
        findings.append(
            f"standards/{name}.md exists but has no on_demand entry in "
            f"rules/index.yml, so no trigger can ever load it."
        )


def check_skills_documented(readme: str, findings: list[str]) -> None:
    listed = set(re.findall(r"\[`/([a-z0-9-]+)`\]\(skills/", readme))
    skills_dir = ROOT / "skills"
    on_disk = {p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()}
    for name in sorted(on_disk - listed):
        findings.append(f"skills/{name}/ has no row in the README skills table.")
    for name in sorted(listed - on_disk):
        findings.append(
            f"README lists /{name} but skills/{name}/SKILL.md does not exist."
        )


def check_agents_documented(readme: str, findings: list[str]) -> None:
    listed = set(re.findall(r"\[`([a-z0-9-]+)`\]\(agents/", readme))
    on_disk = {p.stem for p in (ROOT / "agents").glob("*.md")} - AGENT_NON_AGENTS
    for name in sorted(on_disk - listed):
        findings.append(f"agents/{name}.md has no row in the README agents table.")
    for name in sorted(listed - on_disk - AGENT_NON_AGENTS):
        findings.append(
            f"README lists the {name} agent but agents/{name}.md does not exist."
        )


def check_no_stray_hook_files(findings: list[str]) -> None:
    for path in sorted((ROOT / "hooks").glob("*.py")):
        if TEST_SHAPED.search(path.name):
            findings.append(
                f"hooks/{path.name} is test-shaped but sits in hooks/. The "
                f"file-bypass smoke test executes every hooks/*.py, so this "
                f"runs a test runner as a subprocess and hangs until the "
                f"harness times out. Move it under tests/hooks/."
            )


def check_index_rule_paths(index: dict, findings: list[str]) -> None:
    """An on_demand entry that names a path must name one that resolves."""
    for name, entry in (index.get("on_demand") or {}).items():
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if path and not (ROOT / path).exists():
            findings.append(
                f"rules/index.yml: on_demand '{name}' names a missing {path}"
            )


def main() -> int:
    findings: list[str] = []
    index = load_index()
    readme = (ROOT / "README.md").read_text()

    check_rules_registered(index, findings)
    check_standards_registered(index, findings)
    check_skills_documented(readme, findings)
    check_agents_documented(readme, findings)
    check_no_stray_hook_files(findings)
    check_index_rule_paths(index, findings)

    if findings:
        print(f"FAILED: {len(findings)} registry drift finding(s)\n")
        for finding in findings:
            print(f"  {finding}")
        print("\nEvery artifact on disk must be reachable from the registry")
        print("that is supposed to load or document it.")
        return 1

    print("PASSED: no registry drift. Rules and standards are registered,")
    print("skills and agents are documented, hooks/ holds only hooks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

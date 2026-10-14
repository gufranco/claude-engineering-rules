from __future__ import annotations

import json
import os
import sys
from types import ModuleType

from . import mutation_allowlist_names, mutation_allowlists, mutation_state_patterns

ALLOWLIST_MODULES: tuple[ModuleType, ...] = (
    mutation_allowlists,
    mutation_allowlist_names,
    mutation_state_patterns,
)
CATALOG_FILENAME = "mutation_fix_suggestions.json"
CATALOG_SECTIONS = ("exact", "by_category")
JSON_INDENT = 2


def _is_listed_table(value: object) -> bool:
    return isinstance(value, (tuple, list, set, frozenset)) and not callable(value)


def allowlist_tables() -> dict[str, list[str]]:
    names = sorted(
        {
            name
            for module in ALLOWLIST_MODULES
            for name in dir(module)
            if not name.startswith("_")
        }
    )
    values = {
        name: getattr(module, name)
        for module in reversed(ALLOWLIST_MODULES)
        for name in names
        if hasattr(module, name)
    }
    return {
        name: sorted(map(str, values[name]))
        for name in names
        if _is_listed_table(values[name])
    }


def _catalog_codes(data: object) -> list[str]:
    if not isinstance(data, dict):
        return []
    return sorted(
        {
            str(entry["code"])
            for section in CATALOG_SECTIONS
            for entry in data.get(section, {}).values()
            if isinstance(entry, dict) and entry.get("code")
        }
    )


def _print_detectors(version: str, hooks_dir: str) -> int:
    try:
        with open(os.path.join(hooks_dir, CATALOG_FILENAME), encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        sys.stderr.write(f"failed to read detector catalog: {exc}\n")
        return 1
    payload = {"version": version, "detectors": _catalog_codes(data)}
    sys.stdout.write(json.dumps(payload, indent=JSON_INDENT))
    sys.stdout.write("\n")
    return 0


def _list_allowlists(version: str) -> int:
    payload: dict[str, object] = {"version": version, **allowlist_tables()}
    sys.stdout.write(json.dumps(payload, indent=JSON_INDENT))
    sys.stdout.write("\n")
    return 0


def handle_cli_flags(argv: list[str], version: str, hooks_dir: str) -> int | None:
    if not argv:
        return None
    flag = argv[0]
    if flag in ("--version", "-V"):
        sys.stdout.write(f"mutation-method-blocker {version}\n")
        return 0
    if flag == "--print-detectors":
        return _print_detectors(version, hooks_dir)
    if flag == "--list-allowlists":
        return _list_allowlists(version)
    return None

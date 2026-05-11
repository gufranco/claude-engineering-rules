"""Project-local config loader for the mutation-method-blocker hook.

Plan items 284-287. Reads `<project-root>/.claude/mutation-allowlist.yml`
(or `.json`) and merges entries into the in-memory allowlists. The loader
is intentionally lenient: invalid configs produce a warning to stderr and
the hook continues with built-in defaults. The hook never crashes on
malformed user input.

The project root is discovered by walking parents of the file under analysis
until a `.git` directory or a `package.json` is found. If neither is found,
the config search yields nothing and the hook uses its built-ins.

Schema validation is best-effort: when `jsonschema` is importable, the
config is validated against `~/.claude/schemas/mutation-allowlist.schema.json`.
When `jsonschema` is unavailable (clean machine, restricted environment),
a minimal in-tree validator runs the structural checks the hook depends on
(version is the integer 1, every field is the expected type).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

CONFIG_DIR = ".claude"
CONFIG_BASENAMES: tuple[str, ...] = (
    "mutation-allowlist.yml",
    "mutation-allowlist.yaml",
    "mutation-allowlist.json",
)
PROJECT_MARKER_DIRS: tuple[str, ...] = (".git",)
PROJECT_MARKER_FILES: tuple[str, ...] = ("package.json", "pnpm-workspace.yaml")
SCHEMA_PATH = os.path.expanduser("~/.claude/schemas/mutation-allowlist.schema.json")


@dataclass(frozen=True)
class ProjectConfig:
    """Resolved project-local overrides.

    Each field is empty by default so the merged allowlist equals the
    built-in defaults when no config is present. Frozen so the loaded
    config cannot be mutated by mistake at the call site.
    """

    framework_receivers: frozenset[str] = field(default_factory=frozenset)
    hot_path_segments: tuple[str, ...] = ()
    skip_segments: tuple[str, ...] = ()
    skip_suffixes: tuple[str, ...] = ()
    param_reassign_allowed_names: frozenset[str] = field(default_factory=frozenset)
    disable_detectors: frozenset[str] = field(default_factory=frozenset)
    experimental_detectors: frozenset[str] = field(default_factory=frozenset)


EMPTY_CONFIG = ProjectConfig()


def _warn(msg: str) -> None:
    sys.stderr.write(f"[mutation-method-blocker] config: {msg}\n")


def discover_project_root(start_path: str) -> str | None:
    """Walk parents of `start_path` until a project marker is found.

    Returns the directory containing the marker or None if no marker is
    encountered before the filesystem root. The marker set is fixed: a
    `.git` directory, a `package.json`, or a `pnpm-workspace.yaml`.
    """
    current = os.path.abspath(start_path)
    if os.path.isfile(current):
        current = os.path.dirname(current)
    while True:
        for marker in PROJECT_MARKER_DIRS:
            if os.path.isdir(os.path.join(current, marker)):
                return current
        for marker in PROJECT_MARKER_FILES:
            if os.path.isfile(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def discover_config_path(project_root: str) -> str | None:
    config_dir = os.path.join(project_root, CONFIG_DIR)
    if not os.path.isdir(config_dir):
        return None
    for basename in CONFIG_BASENAMES:
        candidate = os.path.join(config_dir, basename)
        if os.path.isfile(candidate):
            return candidate
    return None


def _parse_yaml_minimal(text: str) -> dict[str, Any]:
    """Parse the constrained YAML subset we accept for the allowlist.

    Supports:
      - top-level scalar: `version: 1`
      - top-level list: `framework_receivers:` followed by `  - name`
      - top-level integer / string scalars
      - line comments starting with `#`

    Anything outside this subset raises ValueError. Users who need richer
    YAML can use the `.json` extension instead, parsed by `json.loads`.
    """
    data: dict[str, Any] = {}
    current_list: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  - "):
            if current_list is None:
                raise ValueError(f"unexpected list item without a key: {raw_line!r}")
            value = line[4:].strip().strip('"').strip("'")
            current_list.append(value)
            continue
        if line.startswith(" "):
            raise ValueError(f"unsupported indentation: {raw_line!r}")
        if ":" not in line:
            raise ValueError(f"missing colon: {raw_line!r}")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not value:
            current_list = []
            data[key] = current_list
            continue
        current_list = None
        if value.lstrip("-").isdigit():
            data[key] = int(value)
        else:
            data[key] = value.strip('"').strip("'")
    return data


def _load_text(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        _warn(f"unable to read {path}: {exc}")
        return None
    if path.endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            _warn(f"invalid JSON in {path}: {exc}")
            return None
    else:
        try:
            data = _parse_yaml_minimal(text)
        except ValueError as exc:
            _warn(f"invalid YAML in {path}: {exc}")
            return None
    if not isinstance(data, dict):
        _warn(f"top-level value in {path} is not a mapping")
        return None
    return data


def _validate_with_jsonschema(data: dict[str, Any]) -> bool:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return _validate_inline(data)
    if not os.path.isfile(SCHEMA_PATH):
        return _validate_inline(data)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        _warn(f"unable to load schema {SCHEMA_PATH}: {exc}")
        return _validate_inline(data)
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        _warn(f"config validation failed: {exc.message}")
        return False
    return True


def _validate_inline(data: dict[str, Any]) -> bool:
    """Minimal structural validation when jsonschema is unavailable."""
    if data.get("version") != 1:
        _warn("config field 'version' must be 1")
        return False
    list_fields = (
        "framework_receivers",
        "hot_path_segments",
        "skip_segments",
        "skip_suffixes",
        "param_reassign_allowed_names",
        "disable_detectors",
        "experimental_detectors",
    )
    for fname in list_fields:
        value = data.get(fname)
        if value is None:
            continue
        if not isinstance(value, list):
            _warn(f"config field '{fname}' must be a list")
            return False
        for item in value:
            if not isinstance(item, str) or not item:
                _warn(f"config field '{fname}' contains non-string or empty item")
                return False
    known = set(list_fields) | {"version"}
    unknown = set(data) - known
    if unknown:
        _warn(f"config has unknown fields (ignored): {sorted(unknown)}")
    return True


def _coerce_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def load_project_config(start_path: str) -> ProjectConfig:
    """Load the project-local config for the file at `start_path`.

    Returns `EMPTY_CONFIG` when no project root is found, no config file
    exists, the file fails to parse, or the file fails schema validation.
    The hook continues with built-in defaults in every failure mode.
    """
    if not start_path:
        return EMPTY_CONFIG
    root = discover_project_root(start_path)
    if root is None:
        return EMPTY_CONFIG
    path = discover_config_path(root)
    if path is None:
        return EMPTY_CONFIG
    data = _load_text(path)
    if data is None:
        return EMPTY_CONFIG
    if not _validate_with_jsonschema(data):
        return EMPTY_CONFIG
    return ProjectConfig(
        framework_receivers=frozenset(_coerce_list(data, "framework_receivers")),
        hot_path_segments=tuple(_coerce_list(data, "hot_path_segments")),
        skip_segments=tuple(_coerce_list(data, "skip_segments")),
        skip_suffixes=tuple(_coerce_list(data, "skip_suffixes")),
        param_reassign_allowed_names=frozenset(
            _coerce_list(data, "param_reassign_allowed_names")
        ),
        disable_detectors=frozenset(_coerce_list(data, "disable_detectors")),
        experimental_detectors=frozenset(_coerce_list(data, "experimental_detectors")),
    )

#!/usr/bin/env python3
from __future__ import annotations

import re
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


PROTECTED_BASENAMES = {
    "tsconfig.json",
    "jsconfig.json",
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.yml",
    ".eslintrc.yaml",
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    "eslint.config.ts",
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.js",
    ".prettierrc.cjs",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    "prettier.config.js",
    "prettier.config.mjs",
    "prettier.config.cjs",
    "biome.json",
    "biome.jsonc",
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "pyrightconfig.json",
    "pyrightconfig.toml",
    "clippy.toml",
    ".clippy.toml",
    "rust-toolchain.toml",
    "rust-toolchain",
    ".golangci.yml",
    ".golangci.yaml",
    ".golangci.toml",
    ".rubocop.yml",
    "detekt.yml",
    "detekt-config.yml",
    "eslint.config.mts",
    "eslint.config.cts",
    "prettier.config.ts",
    "prettier.config.mts",
    ".prettierrc.toml",
    ".bypass-state.json",
}

MIXED_CONFIG_BASENAMES = {"pyproject.toml", "setup.cfg", ".flake8", "tox.ini"}

STRICTNESS_SECTION = re.compile(
    r"\[(?:tool\.(?:ruff|mypy|pyright|pylint|flake8|black)|mypy|flake8|pylint|pycodestyle)\b"
    r"|^\s*(?:extend-)?(?:ignore|select|per-file-ignores|disable|disable_error_code"
    r"|strict|max-line-length|line-length)\s*=",
    re.MULTILINE,
)

PROTECTED_PREFIXES = ("tsconfig.",)

PROTECTED_TSCONFIG_SUFFIXES = (".json",)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def _is_protected(path: str) -> bool:
    base = os.path.basename(path)
    if base in PROTECTED_BASENAMES:
        return True
    if base.startswith(PROTECTED_PREFIXES) and base.endswith(
        PROTECTED_TSCONFIG_SUFFIXES
    ):
        return True
    return False


def _guards(path: str, content: str) -> bool:
    if _is_protected(path):
        return True
    if os.path.basename(path) in MIXED_CONFIG_BASENAMES:
        return STRICTNESS_SECTION.search(content) is not None
    return False


def _proposed_content(tool_input: dict) -> str | None:
    if "content" in tool_input:
        return tool_input.get("content")
    if "new_string" in tool_input:
        return tool_input.get("new_string")
    if "edits" in tool_input and isinstance(tool_input["edits"], list):
        return "\n".join(
            edit.get("new_string", "")
            for edit in tool_input["edits"]
            if isinstance(edit, dict)
        )
    return None


from _lib.hook_profile import should_run  # noqa: E402


def main() -> None:
    if not should_run("config-protection"):
        sys.exit(0)
    if os.environ.get("CONFIG_PROTECTION_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("config-protection"):
        sys.exit(0)
    data = read_hook_payload("config-protection")

    tool_input = data.get("tool_input", data.get("input", {}))
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path or not _guards(file_path, _proposed_content(tool_input) or ""):
        sys.exit(0)

    base = os.path.basename(file_path)
    print(
        f"BLOCKED: edits to `{base}` weaken type or lint strictness for the whole project.\n",
        file=sys.stderr,
    )
    print(
        "The convenient path is to silence the rule in config. That converts a\n"
        "real defect into a silent regression. Fix the offending code instead.\n",
        file=sys.stderr,
    )
    print(
        "Bypass only for legitimate reasons: toolchain version bump, adopting a\n"
        "new rule across the codebase, or following an upstream defaults change.\n"
        "Set CONFIG_PROTECTION_DISABLE=1 in the environment for that single edit.",
        file=sys.stderr,
    )
    _audit(
        hook="config-protection",
        decision="block",
        tool=data.get("tool_name", "Write"),
        reason=f"protected config file: {base}",
        file_path=file_path,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()

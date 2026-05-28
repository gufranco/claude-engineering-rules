#!/usr/bin/env python3
"""Block edits to project linter, formatter, and typechecker configs.

Runs on PreToolUse for Write/Edit/MultiEdit. When the target is a known
config file for a linter, formatter, or typechecker (tsconfig.json,
.eslintrc, ruff.toml, mypy.ini, etc.), block the edit and instruct the
agent to fix the offending code rather than weaken the config.

Rationale: when type checks or lint runs fail, the convenient path is
to silence the rule in config. That converts a real defect into a
silent regression. The rule lives in ~/.claude/CLAUDE.md
"Maximum Compiler and Checker Strictness" and ~/.claude/rules/code-style.md
"Zero Warnings". This hook makes the rule mechanical.

Scope: project-level configs. The hook fires regardless of repo, so it
protects every project the user touches.

Exit 0 = allow, exit 2 = block.

Bypass:
  - Set `CONFIG_PROTECTION_DISABLE=1` for legitimate toolchain bumps
    (raising the TypeScript target, upgrading ESLint major version,
    adopting a new lint rule across the codebase).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


# Exact basenames the hook protects.
PROTECTED_BASENAMES = {
    # TypeScript / JavaScript
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
    # Python
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "pyrightconfig.json",
    "pyrightconfig.toml",
    # Rust
    "clippy.toml",
    ".clippy.toml",
    "rust-toolchain.toml",
    "rust-toolchain",
    # Go
    ".golangci.yml",
    ".golangci.yaml",
    ".golangci.toml",
    # Ruby
    ".rubocop.yml",
    # Java / Kotlin
    "detekt.yml",
    "detekt-config.yml",
}

# Glob-style prefixes for files where any matching basename is protected.
PROTECTED_PREFIXES = ("tsconfig.",)

# Substring markers in tsconfig.* names that should always be protected.
PROTECTED_TSCONFIG_SUFFIXES = (".json",)


def _is_protected(path: str) -> bool:
    base = os.path.basename(path)
    if base in PROTECTED_BASENAMES:
        return True
    if base.startswith(PROTECTED_PREFIXES) and base.endswith(
        PROTECTED_TSCONFIG_SUFFIXES
    ):
        # tsconfig.app.json, tsconfig.node.json, tsconfig.build.json, etc.
        return True
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


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> None:
    if not should_run("config-protection"):
        _sys.exit(0)
    if os.environ.get("CONFIG_PROTECTION_DISABLE") == "1":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", data.get("input", {}))
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path or not _is_protected(file_path):
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

#!/usr/bin/env python3
"""PreToolUse Write/Edit/MultiEdit guard for secrets-bearing files.

Blocks edits on:
    - `.env` and every variant except `.env.example`, `.env.template`,
      `.env.sample`, `.env.defaults`.
    - Files under any `secrets/` or `credentials/` directory.
    - Private key files (`*.pem`, `*.key`, `id_rsa`, `id_ed25519`, `id_ecdsa`, `id_dsa`).
    - Cloud and tool credential files (`~/.aws/credentials`, `~/.docker/config.json`,
      `.npmrc`, `.pypirc`, `.netrc`, `.pgpass`, `.mysql_history`).
    - Kubernetes config (`~/.kube/config`).
    - Terraform state and variable files (`*.tfstate*`, `*.tfvars*`).
    - Credential JSON (`*-credentials.json`, `*_credentials.json`, `service-account*.json`).
    - SSH and GPG directories.

Bypass channels:
    1. Env var `ENV_FILE_GUARD_DISABLE=1` (parent shell).
    2. File registry entry for hook `env-file-guard`.
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402

try:
    from _lib.audit_log import record as _audit_record
except Exception:  # noqa: BLE001
    _audit_record = None  # type: ignore[assignment]

HOOK_NAME = "env-file-guard"
ENV_DISABLE = "ENV_FILE_GUARD_DISABLE"
ALLOWED_ENV_BASENAMES = {
    ".env.example",
    ".env.template",
    ".env.sample",
    ".env.defaults",
}
PRIVATE_KEY_GLOBS = ("*.pem", "*.key")
PRIVATE_KEY_NAMES = {"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"}
CRED_CONFIG_NAMES = {".npmrc", ".pypirc", ".netrc", ".pgpass", ".mysql_history"}
CREDENTIAL_JSON_GLOBS = (
    "*-credentials.json",
    "*_credentials.json",
    "service-account*.json",
)
TFSTATE_GLOBS = ("*.tfstate", "*.tfstate.backup")
TFVARS_GLOBS = ("*.tfvars", "*.tfvars.json")


def _read_payload() -> tuple[str, str]:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or data.get("input") or {}
    if not isinstance(tool_input, dict):
        return tool if isinstance(tool, str) else "", ""
    path = tool_input.get("file_path", "")
    return (tool if isinstance(tool, str) else ""), (
        path if isinstance(path, str) else ""
    )


def _audit(reason: str, tool: str, file_path: str) -> None:
    if _audit_record is None:
        return
    try:
        _audit_record(
            hook=HOOK_NAME,
            decision="block",
            decision_class="block",
            reason=reason,
            tool=tool,
            command_excerpt=file_path[:200],
        )
    except Exception:  # noqa: BLE001
        pass


def _match_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def _classify(file_path: str) -> tuple[str, str] | None:
    basename = os.path.basename(file_path)
    posix = file_path.replace("\\", "/")
    if basename in ALLOWED_ENV_BASENAMES:
        return None
    if basename == ".env" or basename.startswith(".env."):
        return (
            "env file write blocked",
            f"BLOCKED: Cannot modify {basename}. Environment files may contain secrets.\n"
            f"  File: {file_path}\n\n"
            "  If you need to document a new env var, update .env.example instead.\n",
        )
    if "/secrets/" in posix or "/credentials/" in posix:
        return (
            "secrets directory write blocked",
            "BLOCKED: Cannot modify files in secrets directory.\n"
            f"  File: {file_path}\n",
        )
    if basename in PRIVATE_KEY_NAMES or _match_any(basename, PRIVATE_KEY_GLOBS):
        return (
            "private key write blocked",
            f"BLOCKED: Cannot modify private key files.\n  File: {file_path}\n",
        )
    if posix.endswith("/.aws/credentials") or posix.endswith("/.docker/config.json"):
        return (
            "cloud credential file blocked",
            "BLOCKED: Cannot modify cloud/tool credential files.\n"
            f"  File: {file_path}\n",
        )
    if basename in CRED_CONFIG_NAMES:
        return (
            "credential config blocked",
            "BLOCKED: Cannot modify credential/auth config files.\n"
            f"  File: {file_path}\n",
        )
    if posix.endswith("/.kube/config"):
        return (
            "kube config blocked",
            "BLOCKED: Cannot modify Kubernetes config (contains cluster credentials).\n"
            f"  File: {file_path}\n",
        )
    if _match_any(basename, TFSTATE_GLOBS):
        return (
            "tfstate blocked",
            "BLOCKED: Cannot modify Terraform state files (contain infrastructure secrets).\n"
            f"  File: {file_path}\n",
        )
    if _match_any(basename, TFVARS_GLOBS):
        return (
            "tfvars blocked",
            "BLOCKED: Cannot modify Terraform variable files (may contain secrets).\n"
            f"  File: {file_path}\n\n"
            "  Use terraform.tfvars.example for documentation instead.\n",
        )
    if _match_any(basename, CREDENTIAL_JSON_GLOBS):
        return (
            "credential json blocked",
            f"BLOCKED: Cannot modify credential JSON files.\n  File: {file_path}\n",
        )
    if "/.ssh/" in posix or "/.gnupg/" in posix:
        return (
            "ssh/gpg blocked",
            "BLOCKED: Cannot modify SSH/GPG configuration and keys.\n"
            f"  File: {file_path}\n",
        )
    return None


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    tool, file_path = _read_payload()
    if tool not in {"Write", "Edit", "MultiEdit"}:
        return 0
    if not file_path:
        return 0
    classification = _classify(file_path)
    if classification is None:
        return 0
    reason, message = classification
    sys.stderr.write(message)
    _audit(reason, tool, file_path)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

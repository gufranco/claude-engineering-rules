#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import os
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402

from _lib.bypass import is_bypassed  # noqa: E402

from _lib.audit_log import record as _audit_record  # noqa: E402

HOOK_NAME = "env-file-guard"
ENV_DISABLE = "ENV_FILE_GUARD_DISABLE"
ALLOWED_ENV_BASENAMES = {
    ".env.example",
    ".env.template",
    ".env.sample",
    ".env.defaults",
    ".env.test",
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
    data = read_hook_payload("env-file-guard")
    tool = data.get("tool_name", "")
    tool_input = tool_input_of(data)
    path = tool_input.get("file_path", "")
    return (tool if isinstance(tool, str) else ""), (
        path if isinstance(path, str) else ""
    )


def _audit(reason: str, tool: str, file_path: str) -> None:
    _audit_record(
        hook=HOOK_NAME,
        decision="block",
        decision_class="block",
        reason=reason,
        tool=tool,
        command_excerpt=file_path[:200],
    )


def _match_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def _is_env_file(basename: str, posix: str) -> bool:
    return basename == ".env" or basename.startswith(".env.")


def _in_secrets_dir(basename: str, posix: str) -> bool:
    return "/secrets/" in posix or "/credentials/" in posix


def _is_private_key(basename: str, posix: str) -> bool:
    return basename in PRIVATE_KEY_NAMES or _match_any(basename, PRIVATE_KEY_GLOBS)


def _is_cloud_credential(basename: str, posix: str) -> bool:
    return posix.endswith("/.aws/credentials") or posix.endswith("/.docker/config.json")


def _is_credential_config(basename: str, posix: str) -> bool:
    return basename in CRED_CONFIG_NAMES


def _is_kube_config(basename: str, posix: str) -> bool:
    return posix.endswith("/.kube/config")


def _is_tfstate(basename: str, posix: str) -> bool:
    return _match_any(basename, TFSTATE_GLOBS)


def _is_tfvars(basename: str, posix: str) -> bool:
    return _match_any(basename, TFVARS_GLOBS)


def _is_credential_json(basename: str, posix: str) -> bool:
    return _match_any(basename, CREDENTIAL_JSON_GLOBS)


def _in_ssh_or_gnupg(basename: str, posix: str) -> bool:
    return "/.ssh/" in posix or "/.gnupg/" in posix


RULES: tuple[tuple[Callable[[str, str], bool], str, str], ...] = (
    (
        _is_env_file,
        "env file write blocked",
        "BLOCKED: Cannot modify {basename}. Environment files may contain secrets.\n"
        "  File: {file_path}\n\n"
        "  If you need to document a new env var, update .env.example instead.\n",
    ),
    (
        _in_secrets_dir,
        "secrets directory write blocked",
        "BLOCKED: Cannot modify files in secrets directory.\n  File: {file_path}\n",
    ),
    (
        _is_private_key,
        "private key write blocked",
        "BLOCKED: Cannot modify private key files.\n  File: {file_path}\n",
    ),
    (
        _is_cloud_credential,
        "cloud credential file blocked",
        "BLOCKED: Cannot modify cloud/tool credential files.\n  File: {file_path}\n",
    ),
    (
        _is_credential_config,
        "credential config blocked",
        "BLOCKED: Cannot modify credential/auth config files.\n  File: {file_path}\n",
    ),
    (
        _is_kube_config,
        "kube config blocked",
        "BLOCKED: Cannot modify Kubernetes config (contains cluster credentials).\n"
        "  File: {file_path}\n",
    ),
    (
        _is_tfstate,
        "tfstate blocked",
        "BLOCKED: Cannot modify Terraform state files (contain infrastructure secrets).\n"
        "  File: {file_path}\n",
    ),
    (
        _is_tfvars,
        "tfvars blocked",
        "BLOCKED: Cannot modify Terraform variable files (may contain secrets).\n"
        "  File: {file_path}\n\n"
        "  Use terraform.tfvars.example for documentation instead.\n",
    ),
    (
        _is_credential_json,
        "credential json blocked",
        "BLOCKED: Cannot modify credential JSON files.\n  File: {file_path}\n",
    ),
    (
        _in_ssh_or_gnupg,
        "ssh/gpg blocked",
        "BLOCKED: Cannot modify SSH/GPG configuration and keys.\n  File: {file_path}\n",
    ),
)


def _classify(file_path: str) -> tuple[str, str] | None:
    basename = os.path.basename(file_path)
    posix = file_path.replace("\\", "/")
    if basename in ALLOWED_ENV_BASENAMES:
        return None
    for matches, reason, template in RULES:
        if matches(basename, posix):
            return reason, template.format(basename=basename, file_path=file_path)
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

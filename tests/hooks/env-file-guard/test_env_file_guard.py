"""Tests for `hooks/env-file-guard.py`.

Observable behavior: block Write/Edit/MultiEdit on .env files, secrets dirs,
private keys, cloud creds, Kubernetes config, tfstate/tfvars, credential JSON,
SSH/GPG. Allow .env.example, .env.template, .env.sample, .env.defaults.
Bypass via env or file registry.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "env-file-guard.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

_TESTS_DIR = ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402


def _run(
    tool: str, file_path: str, env: dict | None = None
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": file_path}})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=5,
    )


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_blocks_env_file(tool: str) -> None:
    # Arrange
    # Act
    result = _run(tool, "/project/.env")
    # Assert
    assert result.returncode == 2
    assert "Cannot modify .env" in result.stderr


@pytest.mark.parametrize(
    "name",
    [
        ".env.local",
        ".env.production",
        ".env.production.local",
        ".env.docker.local",
        ".env.team",
    ],
)
def test_blocks_env_variants(name: str) -> None:
    # Arrange
    # Act
    result = _run("Write", f"/project/{name}")
    # Assert
    assert result.returncode == 2


@pytest.mark.parametrize(
    "name", [".env.example", ".env.template", ".env.sample", ".env.defaults"]
)
def test_allows_documentation_env_files(name: str) -> None:
    # Arrange
    # Act
    result = _run("Write", f"/project/{name}")
    # Assert
    assert result.returncode == 0


def test_blocks_secrets_directory() -> None:
    # Arrange
    # Act
    result = _run("Write", "/repo/secrets/key.txt")
    # Assert
    assert result.returncode == 2
    assert "secrets directory" in result.stderr


def test_blocks_credentials_directory() -> None:
    # Arrange
    # Act
    result = _run("Write", "/repo/credentials/token.txt")
    # Assert
    assert result.returncode == 2


@pytest.mark.parametrize(
    "name", ["server.pem", "private.key", "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"]
)
def test_blocks_private_keys(name: str) -> None:
    # Arrange
    # Act
    result = _run("Write", f"/project/{name}")
    # Assert
    assert result.returncode == 2
    assert "private key" in result.stderr


def test_blocks_aws_credentials() -> None:
    # Arrange
    # Act
    result = _run("Write", "/home/u/.aws/credentials")
    # Assert
    assert result.returncode == 2
    assert "credential" in result.stderr.lower()


def test_blocks_docker_config() -> None:
    # Arrange
    # Act
    result = _run("Write", "/home/u/.docker/config.json")
    # Assert
    assert result.returncode == 2


@pytest.mark.parametrize(
    "name", [".npmrc", ".pypirc", ".netrc", ".pgpass", ".mysql_history"]
)
def test_blocks_credential_config(name: str) -> None:
    # Arrange
    # Act
    result = _run("Write", f"/home/u/{name}")
    # Assert
    assert result.returncode == 2


def test_blocks_kube_config() -> None:
    # Arrange
    # Act
    result = _run("Write", "/home/u/.kube/config")
    # Assert
    assert result.returncode == 2
    assert "Kubernetes" in result.stderr


@pytest.mark.parametrize("name", ["state.tfstate", "main.tfstate.backup"])
def test_blocks_tfstate(name: str) -> None:
    # Arrange
    # Act
    result = _run("Write", f"/infra/{name}")
    # Assert
    assert result.returncode == 2
    assert "Terraform state" in result.stderr


@pytest.mark.parametrize("name", ["prod.tfvars", "prod.tfvars.json"])
def test_blocks_tfvars(name: str) -> None:
    # Arrange
    # Act
    result = _run("Write", f"/infra/{name}")
    # Assert
    assert result.returncode == 2
    assert "Terraform variable" in result.stderr


@pytest.mark.parametrize(
    "name", ["app-credentials.json", "app_credentials.json", "service-account-key.json"]
)
def test_blocks_credential_json(name: str) -> None:
    # Arrange
    # Act
    result = _run("Write", f"/repo/{name}")
    # Assert
    assert result.returncode == 2


@pytest.mark.parametrize("fragment", [".ssh/id_known", ".gnupg/pubring.kbx"])
def test_blocks_ssh_gpg(fragment: str) -> None:
    # Arrange
    # Act
    result = _run("Write", f"/home/u/{fragment}")
    # Assert
    assert result.returncode == 2


def test_ignores_other_tools() -> None:
    # Arrange
    # Act
    result = _run("Bash", "/project/.env")
    # Assert
    assert result.returncode == 0


def test_ignores_empty_path() -> None:
    # Arrange
    # Act
    result = _run("Write", "")
    # Assert
    assert result.returncode == 0


def test_allows_regular_file() -> None:
    # Arrange
    # Act
    result = _run("Write", "/project/src/main.ts")
    # Assert
    assert result.returncode == 0


def test_env_disable_short_circuits() -> None:
    # Arrange
    # Act
    result = _run("Write", "/project/.env", env={"ENV_FILE_GUARD_DISABLE": "1"})
    # Assert
    assert result.returncode == 0


def test_file_bypass_short_circuits(tmp_path: Path) -> None:
    # Arrange
    state = tmp_path / "state.json"
    set_bypass("env-file-guard", ttl_seconds=120, state_path=state)
    # Act
    result = _run("Write", "/project/.env", env={"CLAUDE_BYPASS_STATE": str(state)})
    # Assert
    assert result.returncode == 0


def test_handles_malformed_json() -> None:
    # Arrange
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env(os.environ.copy()),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0


def test_handles_non_dict_root() -> None:
    # Arrange
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="[1, 2, 3]",
        capture_output=True,
        text=True,
        env=apply_coverage_env(os.environ.copy()),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0


def test_handles_non_dict_tool_input() -> None:
    # Arrange
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input='{"tool_name": "Write", "tool_input": "not a dict"}',
        capture_output=True,
        text=True,
        env=apply_coverage_env(os.environ.copy()),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0


def test_audit_swallows_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    import importlib.util as _util

    spec = _util.spec_from_file_location("_efg_mod1", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def boom(**_kwargs: object) -> None:
        raise RuntimeError("audit explosion")

    monkeypatch.setattr(module, "_audit_record", boom)
    # Act
    module._audit("reason", "Write", "/path")
    # Assert: no exception propagated; coverage of the except branch achieved


def test_audit_noop_when_record_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    import importlib.util as _util

    spec = _util.spec_from_file_location("_efg_mod2", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_audit_record", None)
    # Act
    module._audit("reason", "Write", "/path")
    # Assert: no exception, no record call

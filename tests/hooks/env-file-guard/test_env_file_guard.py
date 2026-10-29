from __future__ import annotations

import importlib.util as _util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.cov_env import apply_coverage_env

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "env-file-guard.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402
from _helpers.audit_log_support import _read_records, isolate_audit_log  # noqa: E402

TIMEOUT_S = 30
ISOLATION = {"CLAUDE_BYPASS_STATE": os.devnull, "CLAUDE_HOOK_AUDIT_DISABLE": "1"}


def _run_raw(stdin: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, **ISOLATION, **(env or {})}),
        timeout=TIMEOUT_S,
        check=False,
    )


def _run(
    tool: str, file_path: str, env: dict | None = None
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": file_path}})
    return _run_raw(payload, env)


def _load(name: str):
    spec = _util.spec_from_file_location(name, str(HOOK))
    assert spec is not None
    assert spec.loader is not None
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_blocks_env_file(tool: str) -> None:
    # Arrange
    file_path = "/project/.env"

    # Act
    result = _run(tool, file_path)

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
    tool = "Write"

    # Act
    result = _run(tool, f"/project/{name}")

    # Assert
    assert result.returncode == 2


@pytest.mark.parametrize(
    "name",
    [".env.example", ".env.template", ".env.sample", ".env.defaults", ".env.test"],
)
def test_allows_documentation_env_files(name: str) -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, f"/project/{name}")

    # Assert
    assert result.returncode == 0


def test_blocks_secrets_directory() -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, "/repo/secrets/key.txt")

    # Assert
    assert result.returncode == 2
    assert "secrets directory" in result.stderr


def test_blocks_credentials_directory() -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, "/repo/credentials/token.txt")

    # Assert
    assert result.returncode == 2


@pytest.mark.parametrize(
    "name", ["server.pem", "private.key", "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"]
)
def test_blocks_private_keys(name: str) -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, f"/project/{name}")

    # Assert
    assert result.returncode == 2
    assert "private key" in result.stderr


def test_blocks_aws_credentials() -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, "/home/u/.aws/credentials")

    # Assert
    assert result.returncode == 2
    assert "credential" in result.stderr.lower()


def test_blocks_docker_config() -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, "/home/u/.docker/config.json")

    # Assert
    assert result.returncode == 2


@pytest.mark.parametrize(
    "name", [".npmrc", ".pypirc", ".netrc", ".pgpass", ".mysql_history"]
)
def test_blocks_credential_config(name: str) -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, f"/home/u/{name}")

    # Assert
    assert result.returncode == 2


def test_blocks_kube_config() -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, "/home/u/.kube/config")

    # Assert
    assert result.returncode == 2
    assert "Kubernetes" in result.stderr


@pytest.mark.parametrize("name", ["state.tfstate", "main.tfstate.backup"])
def test_blocks_tfstate(name: str) -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, f"/infra/{name}")

    # Assert
    assert result.returncode == 2
    assert "Terraform state" in result.stderr


@pytest.mark.parametrize("name", ["prod.tfvars", "prod.tfvars.json"])
def test_blocks_tfvars(name: str) -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, f"/infra/{name}")

    # Assert
    assert result.returncode == 2
    assert "Terraform variable" in result.stderr


@pytest.mark.parametrize(
    "name", ["app-credentials.json", "app_credentials.json", "service-account-key.json"]
)
def test_blocks_credential_json(name: str) -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, f"/repo/{name}")

    # Assert
    assert result.returncode == 2


@pytest.mark.parametrize("fragment", [".ssh/id_known", ".gnupg/pubring.kbx"])
def test_blocks_ssh_gpg(fragment: str) -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, f"/home/u/{fragment}")

    # Assert
    assert result.returncode == 2


def test_ignores_other_tools() -> None:
    # Arrange
    tool = "Bash"

    # Act
    result = _run(tool, "/project/.env")

    # Assert
    assert result.returncode == 0


def test_ignores_empty_path() -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, "")

    # Assert
    assert result.returncode == 0


def test_allows_regular_file() -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, "/project/src/main.ts")

    # Assert
    assert result.returncode == 0


def test_env_disable_short_circuits() -> None:
    # Arrange
    tool = "Write"

    # Act
    result = _run(tool, "/project/.env", env={"ENV_FILE_GUARD_DISABLE": "1"})

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


def test_blocks_malformed_json() -> None:
    # Arrange
    stdin = "not json"

    # Act
    result = _run_raw(stdin)

    # Assert
    assert result.returncode == 2
    assert "could not read its input" in result.stderr


def test_blocks_non_dict_root() -> None:
    # Arrange
    stdin = "[1, 2, 3]"

    # Act
    result = _run_raw(stdin)

    # Assert
    assert result.returncode == 2
    assert "could not read its input" in result.stderr


def test_blocks_non_dict_tool_input() -> None:
    # Arrange
    stdin = '{"tool_name": "Write", "tool_input": "not a dict"}'

    # Act
    result = _run_raw(stdin)

    # Assert
    assert result.returncode == 2
    assert "could not read its input" in result.stderr


def test_audit_records_the_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    module = _load("_efg_mod2")
    log_path = isolate_audit_log(monkeypatch, tmp_path)

    # Act
    module._audit("reason", "Write", "/path")

    # Assert
    record = _read_records(log_path)[-1]
    assert (record["hook"], record["decision"]) == ("env-file-guard", "block")

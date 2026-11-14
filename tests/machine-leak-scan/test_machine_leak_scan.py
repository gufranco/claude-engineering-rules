from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

TOOL = Path(__file__).resolve().parents[2] / "tools" / "machine-leak-scan.py"
FAKER_SEED = 20261117
BLOCK_BYTES = 600 * 1024


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("machine_leak_scan", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def faker() -> Faker:
    generator = Faker()
    generator.seed_instance(FAKER_SEED)
    return generator


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, faker: Faker) -> Path:
    root = tmp_path / faker.lexify("hm????")
    root.mkdir()
    config = root / ".gitconfig"
    config.write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(root))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return root


def _repo(home: Path, files: dict[str, bytes]) -> Path:
    root = home / "src" / "project"
    root.mkdir(parents=True)
    for name, data in files.items():
        (root / name).write_bytes(data)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, timeout=30)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, timeout=30)
    return root


def test_a_clean_repository_exits_zero(home, capsys) -> None:
    # Arrange
    repo = _repo(home, {"a.txt": b"nothing here\n"})

    # Act
    code = _load().main([str(repo)])

    # Assert
    assert (code, capsys.readouterr().out) == (0, "")


def test_a_tracked_home_path_is_reported(home, capsys) -> None:
    # Arrange
    repo = _repo(home, {"a.txt": b"ok\n" + f"root {home}/x\n".encode()})

    # Act
    code = _load().main([str(repo)])

    # Assert
    assert code == 1
    assert (
        capsys.readouterr().out
        == f"{repo}:a.txt:2: home directory path {str(home)!r}\n"
    )


def test_binary_and_oversized_files_are_skipped(home) -> None:
    # Arrange
    leak = str(home).encode()
    files = {"b.bin": b"\0" + leak, "big.txt": leak + b"x" * BLOCK_BYTES}
    repo = _repo(home, files)

    # Act
    code = _load().main([str(repo)])

    # Assert
    assert code == 0


def test_a_deleted_tracked_file_is_skipped(home) -> None:
    # Arrange
    repo = _repo(home, {"gone.txt": str(home).encode()})
    (repo / "gone.txt").unlink()

    # Act
    code = _load().main([str(repo)])

    # Assert
    assert code == 0


def test_a_folder_that_is_not_a_repository_fails_closed(tmp_path, capsys) -> None:
    # Arrange
    folder = tmp_path / "plain"
    folder.mkdir()

    # Act
    code = _load().main([str(folder)])

    # Assert
    assert code == 2
    assert "not a git repository" in capsys.readouterr().err


def test_the_script_runs_from_the_command_line(home) -> None:
    # Arrange
    from _helpers.cov_env import apply_coverage_env

    repo = _repo(home, {"a.txt": b"fine\n"})
    env = apply_coverage_env(dict(os.environ))

    # Act
    done = subprocess.run(
        [sys.executable, str(TOOL), str(repo)],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=False,
    )

    # Assert
    assert (done.returncode, done.stdout) == (0, "")

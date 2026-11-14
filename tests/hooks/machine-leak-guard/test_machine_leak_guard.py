from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from faker import Faker

HOOK = "machine-leak-guard"
FAKER_SEED = 20261116


@dataclass(frozen=True, slots=True)
class Machine:
    home: Path
    area: str
    repo: Path
    env: dict[str, str]


@pytest.fixture
def faker() -> Faker:
    generator = Faker()
    generator.seed_instance(FAKER_SEED)
    return generator


def _git(repo: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        timeout=30,
        env=env,
    )


@pytest.fixture
def machine(tmp_path: Path, faker: Faker) -> Machine:
    home = tmp_path / faker.lexify("hm????")
    area = f"@ {faker.lexify('Zq????').capitalize()}"
    repo = home / area / "project"
    repo.mkdir(parents=True)
    config = home / ".gitconfig"
    config.write_text("[user]\n\tname = t\n\temail = t@t.test\n", encoding="utf-8")
    env = {
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(config),
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    _git(repo, env, "init", "-q")
    _git(repo, env, "config", "commit.gpgsign", "false")
    (repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
    _git(repo, env, "add", "app.py")
    _git(repo, env, "commit", "-q", "--no-verify", "-m", "chore: start")
    return Machine(home, area, repo, env)


def _stage(machine: Machine, name: str, text: str) -> None:
    (machine.repo / name).write_text(text, encoding="utf-8")
    _git(machine.repo, machine.env, "add", name)


def _commit(tool_use, run_hook, machine: Machine, command: str):
    payload = tool_use("Bash", {"command": command}, cwd=str(machine.repo))
    return run_hook(HOOK, payload, env=machine.env)


def test_a_staged_home_path_blocks_the_commit(tool_use, run_hook, machine) -> None:
    # Arrange
    _stage(machine, "app.py", f"print('ok')\nROOT = '{machine.home}/data'\n")

    # Act
    result = _commit(tool_use, run_hook, machine, "git commit -m 'fix: y'")

    # Assert
    assert_blocked(result, "app.py:2: home directory path")


def test_a_local_folder_name_blocks_the_commit(tool_use, run_hook, machine) -> None:
    # Arrange
    _stage(machine, "t.sh", f"cd '/home/u/{machine.area}/x'\n")

    # Act
    result = _commit(tool_use, run_hook, machine, "git commit -m 'test: x'")

    # Assert
    assert_blocked(result, "t.sh:1: local folder name")


def test_a_clean_commit_is_allowed(tool_use, run_hook, machine) -> None:
    # Arrange
    _stage(machine, "app.py", "print('ok')\nROOT = '/home/u/data'\n")

    # Act
    result = _commit(tool_use, run_hook, machine, "git commit -m 'fix: y'")

    # Assert
    assert_allowed(result)


def test_a_line_the_file_already_held_does_not_block(tool_use, run_hook, machine):
    # Arrange
    legacy = f"ROOT = '{machine.home}'\n"
    _stage(machine, "old.py", legacy)
    _git(machine.repo, machine.env, "commit", "-q", "--no-verify", "-m", "chore: x")
    _stage(machine, "old.py", legacy + "VALUE = 1\n")

    # Act
    result = _commit(tool_use, run_hook, machine, "git commit -m 'fix: y'")

    # Assert
    assert_allowed(result)


def test_the_commit_message_is_scanned(tool_use, run_hook, machine) -> None:
    # Arrange
    _stage(machine, "app.py", "print('ok')\nVALUE = 2\n")
    command = f"git commit -m 'fix: path under {machine.area}'"

    # Act
    result = _commit(tool_use, run_hook, machine, command)

    # Assert
    assert_blocked(result, "commit message:1: local folder name")


def test_a_message_file_is_scanned(tool_use, run_hook, machine, tmp_path) -> None:
    # Arrange
    _stage(machine, "app.py", "print('ok')\nVALUE = 3\n")
    message = tmp_path / "msg.txt"
    message.write_text(f"fix: y\n\nseen in {machine.home}\n", encoding="utf-8")

    # Act
    result = _commit(tool_use, run_hook, machine, f"git commit -F {message}")

    # Assert
    assert_blocked(result, "commit message:3: home directory path")


def test_a_file_added_in_the_same_command_is_scanned(tool_use, run_hook, machine):
    # Arrange
    (machine.repo / "new.md").write_text(f"see {machine.area}\n", encoding="utf-8")
    command = "git add new.md && git commit -m 'docs: x'"

    # Act
    result = _commit(tool_use, run_hook, machine, command)

    # Assert
    assert_blocked(result, "new.md:1: local folder name")


def test_commit_all_scans_unstaged_tracked_changes(tool_use, run_hook, machine):
    # Arrange
    (machine.repo / "app.py").write_text(f"X = '{machine.home}'\n", encoding="utf-8")

    # Act
    result = _commit(tool_use, run_hook, machine, "git commit -am 'fix: y'")

    # Assert
    assert_blocked(result, "app.py:1: home directory path")


def test_a_pull_request_body_is_scanned(tool_use, run_hook, machine) -> None:
    # Arrange
    command = f"gh pr create --title 'fix: y' --body 'ran in {machine.home}/x'"

    # Act
    result = _commit(tool_use, run_hook, machine, command)

    # Assert
    assert_blocked(result, "pull request or issue text:1: home directory path")


def test_a_body_file_is_scanned(tool_use, run_hook, machine, tmp_path) -> None:
    # Arrange
    body = tmp_path / "body.md"
    body.write_text(f"Evidence\n\nsee {machine.area}\n", encoding="utf-8")
    command = f"gh issue comment 4 --body-file {body}"

    # Act
    result = _commit(tool_use, run_hook, machine, command)

    # Assert
    assert_blocked(result, "pull request or issue text:3: local folder name")


def test_a_read_only_gh_call_is_allowed(tool_use, run_hook, machine) -> None:
    # Arrange
    command = f"gh pr view 4 --repo x/{machine.area.strip('@ ')}"

    # Act
    result = _commit(tool_use, run_hook, machine, command)

    # Assert
    assert_allowed(result)


def test_an_unrelated_command_is_allowed(tool_use, run_hook, machine) -> None:
    # Arrange
    command = f"ls '{machine.home}'"

    # Act
    result = _commit(tool_use, run_hook, machine, command)

    # Assert
    assert_allowed(result)


def test_the_disable_variable_skips_the_check(tool_use, run_hook, machine) -> None:
    # Arrange
    _stage(machine, "app.py", f"X = '{machine.home}'\n")
    payload = tool_use(
        "Bash", {"command": "git commit -m 'f: y'"}, cwd=str(machine.repo)
    )
    env = {**machine.env, "MACHINE_LEAK_DISABLE": "1"}

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_the_report_explains_the_fix(tool_use, run_hook, machine) -> None:
    # Arrange
    _stage(machine, "app.py", f"X = '{machine.home}'\n")

    # Act
    result = _commit(tool_use, run_hook, machine, "git commit -m 'fix: y'")

    # Assert
    _code, stderr = assert_blocked(result, "machine-identifiers.txt")
    assert "neutral" in stderr


def test_an_unparseable_body_is_scanned_whole(tool_use, run_hook, machine) -> None:
    # Arrange
    command = f"gh pr create --body 'unterminated {machine.home}"

    # Act
    result = _commit(tool_use, run_hook, machine, command)

    # Assert
    assert_blocked(result, "home directory path")


def test_a_tool_other_than_bash_is_allowed(tool_use, run_hook, machine) -> None:
    # Arrange
    payload = tool_use("Write", {"file_path": "a.txt", "content": str(machine.home)})

    # Act
    result = run_hook(HOOK, payload, env=machine.env)

    # Assert
    assert_allowed(result)


def test_an_unreadable_index_fails_closed(tool_use, run_hook, machine) -> None:
    # Arrange
    broken = machine.repo / "broken-index"
    broken.write_bytes(b"not an index")
    payload = tool_use(
        "Bash", {"command": "git commit -m 'f: y'"}, cwd=str(machine.repo)
    )
    env = {**machine.env, "GIT_INDEX_FILE": str(broken)}

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "could not read what this commit records")

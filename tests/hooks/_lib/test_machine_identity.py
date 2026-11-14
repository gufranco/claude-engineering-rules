from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.machine_identity import Kind, discover, is_generic  # noqa: E402

FAKER_SEED = 20261114


@pytest.fixture
def faker() -> Faker:
    generator = Faker()
    generator.seed_instance(FAKER_SEED)
    return generator


def _coined(faker: Faker) -> str:
    return faker.lexify("Zq??vor").capitalize()


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


def _git_config(home: Path, *args: str) -> None:
    subprocess.run(["git", "config", "--global", *args], check=True, timeout=30)


def _tokens(found: list, kind: Kind) -> set[str]:
    return {i.token for i in found if i.kind is kind}


def test_the_home_path_and_its_slug_are_identifiers(home: Path) -> None:
    # Arrange
    repo = home / "repo"

    # Act
    found = discover(home, repo)

    # Assert
    assert _tokens(found, Kind.HOME_PATH) == {str(home), str(home).replace("/", "-")}


def test_the_git_name_and_its_distinctive_parts_are_identifiers(home, faker) -> None:
    # Arrange
    first, last = _coined(faker), _coined(faker)
    _git_config(home, "user.name", f"{first} de {last}")

    # Act
    found = discover(home, home / "repo")

    # Assert
    names = _tokens(found, Kind.REAL_NAME)
    assert {f"{first} de {last}", first, last} <= names
    assert "de" not in names


def test_emails_come_from_global_and_included_configs(home, faker) -> None:
    # Arrange
    direct, included = faker.email(), faker.email()
    extra = home / ".gitconfig-work"
    extra.write_text(f"[user]\n\temail = {included}\n", encoding="utf-8")
    _git_config(home, "user.email", direct)
    _git_config(home, "includeIf.gitdir:~/w/.path", str(extra))

    # Act
    found = discover(home, home / "repo")

    # Assert
    assert {direct, included} <= _tokens(found, Kind.EMAIL)


def test_a_noreply_forge_address_is_not_an_identifier(home, faker) -> None:
    # Arrange
    _git_config(home, "user.email", f"{faker.user_name()}@users.noreply.github.com")

    # Act
    found = discover(home, home / "repo")

    # Assert
    assert _tokens(found, Kind.EMAIL) == set()


def test_workspace_folders_and_their_siblings_are_identifiers(home, faker) -> None:
    # Arrange
    sync, area, client = _coined(faker), f"@ {_coined(faker)}", _coined(faker)
    repo = home / sync / area / "project"
    repo.mkdir(parents=True)
    (home / sync / client).mkdir()
    (home / sync / area / "neighbour").mkdir()

    # Act
    found = discover(home, repo)

    # Assert
    names = _tokens(found, Kind.WORKSPACE)
    assert {sync, area, client, f"{sync}/{area}"} <= names
    assert {"project", "neighbour"}.isdisjoint(names)


def test_a_generic_folder_name_is_not_an_identifier(home) -> None:
    # Arrange
    repo = home / "Workspace" / "project"
    repo.mkdir(parents=True)

    # Act
    found = discover(home, repo)

    # Assert
    assert "Workspace" not in _tokens(found, Kind.WORKSPACE)


def test_a_repository_outside_home_has_no_workspace_names(home, tmp_path) -> None:
    # Arrange
    repo = tmp_path / "outside" / "project"

    # Act
    found = discover(home, repo)

    # Assert
    assert _tokens(found, Kind.WORKSPACE) == set()


def test_the_local_list_adds_and_exempts_names(home, faker) -> None:
    # Arrange
    added, exempted = _coined(faker), _coined(faker)
    (home / ".claude").mkdir()
    listing = f"# note\n{added}\n!{exempted}\n"
    (home / ".claude" / "machine-identifiers.txt").write_text(listing, encoding="utf-8")
    repo = home / exempted / "project"
    repo.mkdir(parents=True)

    # Act
    found = discover(home, repo)

    # Assert
    tokens = {i.token for i in found}
    assert added in _tokens(found, Kind.LISTED)
    assert exempted not in tokens


def test_live_session_ids_are_identifiers(home, faker) -> None:
    # Arrange
    session = faker.uuid4()
    folder = home / ".claude" / "sessions"
    folder.mkdir(parents=True)
    (folder / "1.json").write_text(json.dumps({"sessionId": session}), encoding="utf-8")
    (folder / "2.json").write_text("{not json", encoding="utf-8")

    # Act
    found = discover(home, home / "repo")

    # Assert
    assert _tokens(found, Kind.SESSION_ID) == {session}


def test_the_agent_temp_folder_carries_the_real_uid(home) -> None:
    # Arrange
    expected = f"claude-{os.getuid()}"

    # Act
    found = discover(home, home / "repo")

    # Assert
    assert expected in _tokens(found, Kind.TEMP_PATH)


@pytest.mark.parametrize("token", ["ab", "personal", "house", "git"])
def test_short_dictionary_folder_and_command_words_are_generic(token: str) -> None:
    # Arrange
    dictionary = frozenset({"house"})

    # Act
    result = is_generic(token, dictionary)

    # Assert
    assert result is True


def test_a_coined_word_is_not_generic(faker) -> None:
    # Arrange
    token = _coined(faker)

    # Act
    result = is_generic(token, frozenset({"house"}))

    # Assert
    assert result is False


def test_folders_inside_an_enclosing_repository_are_not_identifiers(home, faker):
    # Arrange
    area, outer = _coined(faker), _coined(faker)
    (home / area / outer / ".git").mkdir(parents=True)
    (home / area / outer / "docs").mkdir()
    repo = home / area / outer / "vendor" / "inner"
    repo.mkdir(parents=True)

    # Act
    found = discover(home, repo)

    # Assert
    assert _tokens(found, Kind.WORKSPACE) == {area}


@pytest.mark.parametrize("token", ["houses", "projects", "Dropbox", "OneDrive"])
def test_plurals_and_sync_products_are_generic(token: str) -> None:
    # Arrange
    dictionary = frozenset({"house"})

    # Act
    result = is_generic(token, dictionary)

    # Assert
    assert result is True


def test_a_missing_tool_contributes_nothing(home, faker, monkeypatch, tmp_path):
    # Arrange
    _git_config(home, "user.email", faker.email())
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    # Act
    found = discover(home, home / "repo")

    # Assert
    assert _tokens(found, Kind.EMAIL) == set()


def test_a_tool_that_cannot_start_contributes_nothing(home, monkeypatch, tmp_path):
    # Arrange
    folder = tmp_path / "broken-bin"
    folder.mkdir()
    broken = folder / "tmux"
    broken.write_bytes(b"\x00\x01not a program")
    broken.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")

    # Act
    found = discover(home, home / "repo")

    # Assert
    assert _tokens(found, Kind.WINDOW) == set()


def test_a_tool_that_hangs_contributes_nothing(home, monkeypatch, tmp_path):
    # Arrange
    folder = tmp_path / "slow-bin"
    folder.mkdir()
    slow = folder / "tmux"
    slow.write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
    slow.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")

    # Act
    found = discover(home, home / "repo")

    # Assert
    assert _tokens(found, Kind.WINDOW) == set()


def test_a_missing_dictionary_keeps_coined_names(home, faker, monkeypatch, tmp_path):
    # Arrange
    import _lib.machine_identity as identity

    area = _coined(faker)
    repo = home / area / "project"
    repo.mkdir(parents=True)
    monkeypatch.setattr(identity, "DICTIONARY", tmp_path / "no-words")

    # Act
    found = discover(home, repo)

    # Assert
    assert area in _tokens(found, Kind.WORKSPACE)


def test_ancestors_that_do_not_exist_list_no_siblings(home, faker) -> None:
    # Arrange
    outer, inner = _coined(faker), _coined(faker)
    repo = home / outer / inner / "project"

    # Act
    found = discover(home, repo)

    # Assert
    assert _tokens(found, Kind.WORKSPACE) == {outer, inner, f"{outer}/{inner}"}


def _fake_gh(tmp_path: Path, logins: list[str]) -> Path:
    folder = tmp_path / "gh-bin"
    folder.mkdir()
    script = folder / "gh"
    lines = "".join(
        f"echo '  Logged in to github.com account {n} (keyring)'\n" for n in logins
    )
    script.write_text(f"#!/bin/sh\n{lines}", encoding="utf-8")
    script.chmod(0o755)
    return folder


def test_other_forge_accounts_and_orgs_are_identifiers(
    home, faker, monkeypatch, tmp_path
):
    # Arrange
    login, org, folder = (
        faker.lexify("acct????"),
        faker.lexify("org????"),
        _coined(faker),
    )
    bin_dir = _fake_gh(tmp_path, [login, home.name])
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    target = home / ".gitconfig-other"
    target.write_text("", encoding="utf-8")
    _git_config(
        home,
        f"includeIf.hasconfig:remote.*.url:git@github.com:{org}/**.path",
        str(target),
    )
    _git_config(home, f"includeIf.gitdir/i:**/{folder} two/.path", str(target))
    monkeypatch.setenv("USER", home.name)

    # Act
    found = discover(home, home / "repo")

    # Assert
    assert _tokens(found, Kind.ACCOUNT) == {login, org, f"{folder} two"}


def test_an_included_path_with_a_space_in_its_condition_is_read(home, faker) -> None:
    # Arrange
    email, folder = faker.email(), _coined(faker)
    target = home / ".gitconfig-spaced"
    target.write_text(f"[user]\n\temail = {email}\n", encoding="utf-8")
    _git_config(home, f"includeIf.gitdir/i:**/{folder} two/.path", str(target))

    # Act
    found = discover(home, home / "repo")

    # Assert
    assert email in _tokens(found, Kind.EMAIL)


def test_the_repository_owner_is_not_an_identifier(home, faker, monkeypatch, tmp_path):
    # Arrange
    org = faker.lexify("org????")
    target = home / ".gitconfig-other"
    target.write_text("", encoding="utf-8")
    _git_config(
        home,
        f"includeIf.hasconfig:remote.*.url:git@github.com:{org}/**.path",
        str(target),
    )
    repo = home / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, timeout=30)
    url = f"git@github.com:{org}/app.git"
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", url], check=True, timeout=30
    )

    # Act
    found = discover(home, repo)

    # Assert
    assert org not in {i.token for i in found}

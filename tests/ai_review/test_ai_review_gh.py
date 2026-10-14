from __future__ import annotations

from pathlib import Path

import pytest

from _helpers.ai_review_support import (
    ai_review,
    run,
)


def garbage_runner(_args: list[str], _token: str) -> str:
    return "<html>"


ALIASES = {"github-work": "github.com", "gitlab-work": "gitlab.com"}


def resolve(host: str) -> str:
    return ALIASES.get(host, host)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("git@github.com:acme/app.git", ("acme", "app")),
        ("https://github.com/acme/app", ("acme", "app")),
        ("https://git::@github.com/acme/app", ("acme", "app")),
        ("ssh://git@github.com/acme/app.git", ("acme", "app")),
        ("git@github-work:acme/app.git", ("acme", "app")),
        ("git@gitlab-work:acme/app.git", None),
        ("https://gitlab.com/acme/app.git", None),
        ("not a url", None),
        ("", None),
    ],
)
def test_parse_remote_resolves_ssh_aliases(url, expected):
    # Arrange
    url_input = url

    # Act
    parsed = ai_review.parse_remote(url_input, resolve)

    # Assert
    assert parsed == expected


def test_parse_remote_defaults_to_the_literal_host():
    # Arrange
    url = "git@github-work:acme/app.git"

    # Act
    parsed = ai_review.parse_remote(url)

    # Assert
    assert parsed is None


def test_pr_urls_are_read_from_output():
    # Arrange
    output = "Creating pull request\nhttps://github.com/acme/app/pull/4290\n"

    # Act
    targets = ai_review.pr_urls(output)

    # Assert
    assert targets == (ai_review.Target("acme", "app", 4290),)


def fake_gh_on_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script: str
) -> None:
    binary = tmp_path / "bin" / "gh"
    binary.parent.mkdir()
    binary.write_text(f"#!/bin/sh\n{script}\n")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary.parent}:/usr/bin:/bin")


def test_run_gh_passes_the_token_and_returns_stdout(monkeypatch, tmp_path):
    # Arrange
    fake_gh_on_path(monkeypatch, tmp_path, 'echo "$GH_TOKEN $*"')

    # Act
    out = ai_review.run_gh(["api", "user"], "tok123")

    # Assert
    assert out == "tok123 api user\n"


def test_run_gh_raises_on_a_failing_call(monkeypatch, tmp_path):
    # Arrange
    fake_gh_on_path(monkeypatch, tmp_path, "echo 'HTTP 404' >&2; exit 1")

    # Act
    with pytest.raises(ai_review.GhError) as raised:
        ai_review.run_gh(["api", "user"], "tok")

    # Assert
    assert str(raised.value) == "HTTP 404"


def test_run_gh_raises_when_failing_silently(monkeypatch, tmp_path):
    # Arrange
    fake_gh_on_path(monkeypatch, tmp_path, "exit 3")

    # Act
    with pytest.raises(ai_review.GhError) as raised:
        ai_review.run_gh(["api", "user"], "tok")

    # Assert
    assert str(raised.value) == "exit 3"


def test_run_gh_raises_when_gh_is_missing(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("PATH", str(tmp_path))

    # Act
    with pytest.raises(ai_review.GhError) as raised:
        ai_review.run_gh(["api", "user"], "tok")

    # Assert
    assert str(raised.value) == "[Errno 2] No such file or directory: 'gh'"


def test_unreadable_response_raises(account, cache):
    # Arrange
    runner = garbage_runner

    # Act
    with pytest.raises(ai_review.GhError) as raised:
        run(runner, account, cache)

    # Assert
    assert str(raised.value).startswith("unreadable GraphQL response: ")

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import ai_review  # noqa: E402

LOGIN_LENGTH = 12


def login(faker: Faker) -> str:
    return faker.pystr(min_chars=LOGIN_LENGTH, max_chars=LOGIN_LENGTH).lower()


NOTICE = (
    "## Claude Code Review\n\nThis repository is configured for manual code "
    "reviews. Comment `@claude review` for a one-time review, or "
    "`@claude review always` to subscribe this PR to a review on every future push."
)
BUGBOT = "<h3>Bugbot needs on-demand usage enabled</h3>"
NOW = 1_800_000_000.0


Json = dict[str, object]


def node(author: str, body: str) -> Json:
    return {"author": {"login": author}, "body": body}


def repo_payload(
    *,
    reviews: tuple[Json, ...] | list[Json] = (),
    comments: tuple[Json, ...] | list[Json] = (),
    label: bool = False,
    prs: int = 1,
) -> Json:
    pr = {
        "reviews": {"nodes": list(reviews)},
        "comments": {"nodes": list(comments)},
    }
    return {
        "data": {
            "repository": {
                "label": {"name": ai_review.REVIEW_LABEL} if label else None,
                "pullRequests": {"nodes": [pr] * prs},
            }
        }
    }


def pull_payload(
    author: str,
    *,
    state: str = "OPEN",
    labels: tuple[str, ...] | list[str] = (),
    comments: tuple[Json, ...] | list[Json] = (),
    reviews: tuple[Json, ...] | list[Json] = (),
) -> Json:
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "state": state,
                    "author": {"login": author},
                    "labels": {"nodes": [{"name": n} for n in labels]},
                    "comments": {"nodes": list(comments)},
                    "reviews": {"nodes": list(reviews)},
                }
            }
        }
    }


class FakeGh:
    def __init__(self, repo: Json, pull: Json, fail: bool = False) -> None:
        self.repo = repo
        self.pull = pull
        self.fail = fail
        self.calls: list[tuple[list[str], str]] = []

    def __call__(self, args: list[str], token: str) -> str:
        self.calls = [*self.calls, (list(args), token)]
        if self.fail:
            raise ai_review.GhError("HTTP 502")
        joined = " ".join(args)
        if "pullRequests(last" in joined:
            return json.dumps(self.repo)
        if "pullRequest(number" in joined:
            return json.dumps(self.pull)
        return "{}"

    def writes(self) -> list[list[str]]:
        return [a for a, _ in self.calls if "POST" in a]


@pytest.fixture
def account(faker: Faker) -> str:
    return login(faker)


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "profiles.json"


def garbage_runner(_args: list[str], _token: str) -> str:
    return "<html>"


def write_cached_label_profile(cache: Path, at: float) -> None:
    profile = {
        "claude_manual": False,
        "review_label": True,
        "bugbot_unavailable": False,
        "auto_reviewers": [],
    }
    cache.write_text(json.dumps({"acme/app": {"at": at, "profile": profile}}))


def profile_fetches(gh: FakeGh) -> list[list[str]]:
    return [c for c, _ in gh.calls if "pullRequests(last" in " ".join(c)]


def run(
    gh: object,
    account: str,
    cache: Path,
    *,
    dry_run: bool = False,
    now: float = NOW,
    number: int = 42,
) -> str:
    return ai_review.request_reviews(
        ai_review.Target(owner="acme", name="app", number=number),
        account=account,
        token="t0k",
        runner=gh,
        cache_path=cache,
        now=now,
        dry_run=dry_run,
    )


def test_profile_detects_manual_claude_from_a_review_notice():
    # Arrange
    payload = repo_payload(reviews=[node("claude", NOTICE)])

    # Act
    profile = ai_review.build_profile(payload)

    # Assert
    assert profile == ai_review.Profile(
        claude_manual=True,
        review_label=False,
        bugbot_unavailable=False,
        auto_reviewers=(),
    )


def test_profile_detects_label_bugbot_and_auto_reviewers():
    # Arrange
    payload = repo_payload(
        reviews=[node("coderabbitai", "ok"), node("chatgpt-codex-connector", "ok")],
        comments=[node("cursor", BUGBOT)],
        label=True,
    )

    # Act
    profile = ai_review.build_profile(payload)

    # Assert
    assert profile == ai_review.Profile(
        claude_manual=False,
        review_label=True,
        bugbot_unavailable=True,
        auto_reviewers=("chatgpt-codex-connector", "coderabbitai"),
    )


def test_profile_ignores_the_trigger_text_from_a_person(faker: Faker) -> None:
    # Arrange
    payload = repo_payload(comments=[node(login(faker), NOTICE)])

    # Act
    profile = ai_review.build_profile(payload)

    # Assert
    assert profile.claude_manual is False


def test_profile_tolerates_missing_authors_and_bodies():
    # Arrange
    payload = repo_payload(reviews=[{"author": None, "body": None}])

    # Act
    profile = ai_review.build_profile(payload)

    # Assert
    assert profile == ai_review.Profile(False, False, False, ())


def test_new_pr_in_manual_repo_gets_one_always_comment(account, cache):
    # Arrange
    gh = FakeGh(repo_payload(reviews=[node("claude", NOTICE)]), pull_payload(account))

    # Act
    summary = run(gh, account, cache)

    # Assert
    assert (gh.writes(), summary) == (
        [
            [
                "api",
                "repos/acme/app/issues/42/comments",
                "-X",
                "POST",
                "-f",
                "body=@claude review always",
            ]
        ],
        "ai-review: acme/app#42 posted `@claude review always`",
    )


def test_already_subscribed_pr_posts_nothing(account, cache):
    # Arrange
    pull = pull_payload(account, comments=[node(account, "@claude review always")])
    gh = FakeGh(repo_payload(reviews=[node("claude", NOTICE)]), pull)

    # Act
    summary = run(gh, account, cache)

    # Assert
    assert (gh.writes(), summary) == (
        [],
        "ai-review: acme/app#42 claude subscribed",
    )


def test_notice_on_the_pr_itself_is_enough(account, cache):
    # Arrange
    pull = pull_payload(account, reviews=[node("claude", NOTICE)])
    gh = FakeGh(repo_payload(), pull)

    # Act
    run(gh, account, cache)

    # Assert
    assert [a[1] for a in gh.writes()] == ["repos/acme/app/issues/42/comments"]


def test_label_repo_gets_the_label_once(account, cache):
    # Arrange
    gh = FakeGh(repo_payload(label=True), pull_payload(account))

    # Act
    summary = run(gh, account, cache)

    # Assert
    assert (gh.writes(), summary) == (
        [
            [
                "api",
                "repos/acme/app/issues/42/labels",
                "-X",
                "POST",
                "-f",
                "labels[]=claude-review",
            ]
        ],
        "ai-review: acme/app#42 added label `claude-review`",
    )


def test_label_already_present_is_not_added(account, cache):
    # Arrange
    gh = FakeGh(
        repo_payload(label=True), pull_payload(account, labels=["claude-review"])
    )

    # Act
    summary = run(gh, account, cache)

    # Assert
    assert (gh.writes(), summary) == (
        [],
        "ai-review: acme/app#42 label `claude-review` present",
    )


def test_someone_elses_pr_is_never_touched(account, cache, faker: Faker) -> None:
    # Arrange
    gh = FakeGh(
        repo_payload(reviews=[node("claude", NOTICE)], label=True),
        pull_payload(login(faker)),
    )

    # Act
    summary = run(gh, account, cache)

    # Assert
    assert (gh.writes(), summary) == ([], "")


def test_closed_pr_is_never_touched(account, cache):
    # Arrange
    gh = FakeGh(
        repo_payload(reviews=[node("claude", NOTICE)]),
        pull_payload(account, state="MERGED"),
    )

    # Act
    summary = run(gh, account, cache)

    # Assert
    assert (gh.writes(), summary) == ([], "")


def test_dry_run_reports_without_writing(account, cache):
    # Arrange
    gh = FakeGh(repo_payload(reviews=[node("claude", NOTICE)]), pull_payload(account))

    # Act
    summary = run(gh, account, cache, dry_run=True)

    # Assert
    assert (gh.writes(), summary) == (
        [],
        "ai-review: acme/app#42 would post `@claude review always`",
    )


def test_auto_and_unavailable_reviewers_are_reported(account, cache):
    # Arrange
    payload = repo_payload(
        reviews=[node("coderabbitai", "ok")], comments=[node("cursor", BUGBOT)]
    )
    gh = FakeGh(payload, pull_payload(account))

    # Act
    summary = run(gh, account, cache)

    # Assert
    assert summary == (
        "ai-review: acme/app#42 auto coderabbitai, bugbot unavailable (billing)"
    )


def test_repo_with_no_ai_reviewer_reports_nothing(account, cache):
    # Arrange
    gh = FakeGh(repo_payload(), pull_payload(account))

    # Act
    summary = run(gh, account, cache)

    # Assert
    assert summary == "ai-review: acme/app#42 no AI reviewer configured"


def test_a_fresh_cached_profile_skips_the_profile_query(account, cache):
    # Arrange
    write_cached_label_profile(cache, NOW)
    gh = FakeGh(repo_payload(), pull_payload(account))

    # Act
    summary = run(gh, account, cache, now=NOW + 60)

    # Assert
    assert profile_fetches(gh) == []
    assert summary == "ai-review: acme/app#42 added label `claude-review`"


def test_expired_cache_is_refreshed(account, cache):
    # Arrange
    write_cached_label_profile(cache, NOW)
    gh = FakeGh(repo_payload(), pull_payload(account))

    # Act
    summary = run(gh, account, cache, now=NOW + ai_review.PROFILE_TTL_SECONDS + 1)

    # Assert
    assert len(profile_fetches(gh)) == 1
    assert summary == "ai-review: acme/app#42 no AI reviewer configured"


def test_corrupt_cache_is_rebuilt(account, cache):
    # Arrange
    cache.write_text("{not json")
    gh = FakeGh(repo_payload(label=True), pull_payload(account))

    # Act
    summary = run(gh, account, cache)

    # Assert
    assert summary == "ai-review: acme/app#42 added label `claude-review`"


def test_api_failure_raises_gh_error(account, cache):
    # Arrange
    gh = FakeGh(repo_payload(), pull_payload(account), fail=True)

    # Act
    with pytest.raises(ai_review.GhError) as raised:
        run(gh, account, cache)

    # Assert
    assert str(raised.value) == "HTTP 502"


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

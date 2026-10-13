from __future__ import annotations


import pytest


from _helpers.raising import raising  # noqa: E402

from _ai_review_request_support import (
    Deps,
    _git_with_remote,
    _recording,
    _request_failing_for,
    login,
    payload,
)


def test_pr_create_uses_the_url_and_the_named_account(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me)
    command = f"GH_TOKEN=$(gh auth token --user {me}) gh pr create --fill"

    # Act
    summaries = hook.handle(
        payload(command, "https://github.com/acme/app/pull/4290\n"), deps.bundle()
    )

    # Assert
    assert (summaries, deps.requests) == (
        ["ai-review: acme/app#4290 ok"],
        [("acme/app#4290", me)],
    )


def test_pr_create_without_a_url_does_nothing(hook):
    # Arrange
    deps = Deps(hook, owner_of_pr=login())

    # Act
    summaries = hook.handle(payload("gh pr create --fill", "error"), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == ([], [])


def test_pr_ready_with_a_number(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me)

    # Act
    summaries = hook.handle(
        payload(f"GH_TOKEN=$(gh auth token --user {me}) gh pr ready 31"),
        deps.bundle(),
    )

    # Assert
    assert deps.requests == [("acme/app#31", me)]
    assert summaries == ["ai-review: acme/app#31 ok"]


def test_pr_ready_with_a_url(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me)
    command = (
        f"GH_TOKEN=$(gh auth token --user {me}) gh pr ready "
        "https://github.com/other/repo/pull/9"
    )

    # Act
    hook.handle(payload(command), deps.bundle())

    # Assert
    assert deps.requests == [("other/repo#9", me)]


def test_pr_ready_without_an_argument_uses_the_branch(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, branch_pr=55)

    # Act
    hook.handle(
        payload(f"GH_TOKEN=$(gh auth token --user {me}) gh pr ready"), deps.bundle()
    )

    # Assert
    assert deps.requests == [("acme/app#55", me)]


def test_push_tries_accounts_until_the_author_matches(hook):
    # Arrange
    me = login()
    other = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[other, me])

    # Act
    summaries = hook.handle(payload("git push -u origin feature/x"), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == (
        ["ai-review: acme/app#7 ok"],
        [("acme/app#7", other), ("acme/app#7", me)],
    )


def test_push_with_no_open_pr_does_nothing(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[me], branch_pr=None)

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == ([], [])


def test_push_to_someone_elses_pr_reports_nothing(hook):
    # Arrange
    deps = Deps(hook, owner_of_pr=login(), accounts=[login(), login()])

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert summaries == []


def test_git_dash_c_and_cd_change_the_directory(hook):
    # Arrange
    me = login()
    seen: list[str] = []
    deps = Deps(hook, owner_of_pr=me, accounts=[me])
    deps.git = _recording(deps.git, seen)

    # Act
    hook.handle(payload("cd sub && git -C inner push"), deps.bundle())

    # Assert
    assert set(seen) == {"/work/sub/inner"}


def test_non_github_remote_is_ignored(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[me])
    deps.git = lambda args, cwd: "https://gitlab.com/acme/app.git\n"

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == ([], [])


def test_a_failing_account_is_skipped(hook):
    # Arrange
    me = login()
    bad = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[bad, me])
    deps.request = _request_failing_for(
        deps.request, bad, hook.ai_review.GhError("HTTP 404")
    )

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert summaries == ["ai-review: acme/app#7 ok"]


def test_every_account_failing_is_reported(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[me])
    deps.request = raising(hook.ai_review.GhError("HTTP 502"))

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert summaries == ["ai-review: acme/app#7 failed: HTTP 502"]


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "echo 'gh pr create'",
        "git pull",
        "gh pr view 3",
        "cat <<'EOF'\ngit push\nEOF",
    ],
)
def test_unrelated_commands_do_nothing(hook, command):
    # Arrange
    deps = Deps(hook, owner_of_pr=login(), accounts=[login()])

    # Act
    summaries = hook.handle(payload(command), deps.bundle())

    # Assert
    assert (summaries, deps.requests) == ([], [])


def test_non_bash_tool_does_nothing(hook):
    # Arrange
    deps = Deps(hook, owner_of_pr=login())

    # Act
    summaries = hook.handle({"tool_name": "Write", "tool_input": {}}, deps.bundle())

    # Assert
    assert summaries == []


def test_accounts_are_capped(hook):
    # Arrange
    me = login()
    many = [login() for _ in range(hook.MAX_ACCOUNTS + 3)] + [me]
    deps = Deps(hook, owner_of_pr=me, accounts=many)

    # Act
    hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert len(deps.requests) == hook.MAX_ACCOUNTS


def test_push_through_an_ssh_alias_reaches_github(hook):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me, accounts=[me])
    deps.git = _git_with_remote("git@github-work:acme/app.git\n")

    # Act
    summaries = hook.handle(payload("git push"), deps.bundle())

    # Assert
    assert summaries == ["ai-review: acme/app#7 ok"]


@pytest.mark.parametrize(
    "flag", ["--repo other/thing", "-R other/thing", "--repo=other/thing"]
)
def test_ready_honors_an_explicit_repository(hook, flag):
    # Arrange
    me = login()
    deps = Deps(hook, owner_of_pr=me)
    command = f"GH_TOKEN=$(gh auth token --user {me}) gh pr ready 12 {flag}"

    # Act
    hook.handle(payload(command), deps.bundle())

    # Assert
    assert deps.requests == [("other/thing#12", me)]

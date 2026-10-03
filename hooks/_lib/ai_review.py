"""Ask every AI reviewer a repository supports to review my pull request.

The repository profile comes from its 20 most recent pull requests: a
`claude` review carrying the manual-mode notice means the Claude GitHub App
waits for `@claude review always`, a `claude-review` label means a
label-gated review workflow, and CodeRabbit or Codex reviews mean those run
on their own. Only an open pull request authored by the acting account is
touched, and every action is skipped when it is already in place.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

CLAUDE_BOT = "claude"
CLAUDE_TRIGGER = "@claude review always"
REVIEW_LABEL = "claude-review"
BUGBOT_BOT = "cursor"
BUGBOT_BILLING = "Bugbot needs on-demand usage"
AUTO_REVIEWERS = ("chatgpt-codex-connector", "coderabbitai")
RECENT_PRS = 20
PROFILE_TTL_SECONDS = 7 * 24 * 60 * 60
GH_TIMEOUT_SECONDS = 20
CACHE_PATH = Path.home() / ".claude" / "cache" / "ai-review-profiles.json"

PROFILE_QUERY = (
    """query($owner: String!, $name: String!, $label: String!) {
  repository(owner: $owner, name: $name) {
    label(name: $label) { name }
    pullRequests(last: %d) { nodes {
      reviews(first: 20) { nodes { author { login } body } }
      comments(first: 30) { nodes { author { login } body } }
    } }
  }
}"""
    % RECENT_PRS
)

PULL_QUERY = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      state
      author { login }
      labels(first: 50) { nodes { name } }
      comments(last: 100) { nodes { author { login } body } }
      reviews(first: 20) { nodes { author { login } body } }
    }
  }
}"""

REMOTE = re.compile(
    r"^(?:[a-z+]+://)?(?:[^@/\s]*@)?([^:/\s]+)[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$"
)
GITHUB_HOST = "github.com"
PR_URL = re.compile(r"https://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)")

Runner = Callable[[Sequence[str], str], str]


class GhError(RuntimeError):
    """A GitHub CLI call failed or returned something unreadable."""


class ActionKind(str, Enum):
    COMMENT = "comment"
    LABEL = "label"


@dataclass(frozen=True)
class Target:
    owner: str
    name: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class Profile:
    claude_manual: bool
    review_label: bool
    bugbot_unavailable: bool
    auto_reviewers: tuple[str, ...]


@dataclass(frozen=True)
class PullState:
    open: bool
    author: str
    labels: tuple[str, ...]
    comments: tuple[tuple[str, str], ...]
    claude_notice: bool


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    value: str


def run_gh(args: Sequence[str], token: str) -> str:
    """Run the GitHub CLI as the account `token` belongs to."""
    env = {**os.environ, "GH_TOKEN": token}
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=GH_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GhError(str(exc)) from exc
    if proc.returncode != 0:
        raise GhError(proc.stderr.strip()[:200] or f"exit {proc.returncode}")
    return proc.stdout


def _authored(nodes: object) -> list[tuple[str, str]]:
    items = nodes if isinstance(nodes, list) else []
    return [
        (((n.get("author") or {}).get("login") or ""), (n.get("body") or ""))
        for n in items
        if isinstance(n, dict)
    ]


def _is_notice(login: str, body: str) -> bool:
    return login == CLAUDE_BOT and CLAUDE_TRIGGER in body


def build_profile(payload: dict) -> Profile:
    """Read the reviewer setup out of the recent pull requests of a repo."""
    repo = payload["data"]["repository"]
    authored = [
        pair
        for pr in repo["pullRequests"]["nodes"]
        for pair in _authored(pr["reviews"]["nodes"])
        + _authored(pr["comments"]["nodes"])
    ]
    logins = {login for login, _ in authored}
    return Profile(
        claude_manual=any(_is_notice(lg, body) for lg, body in authored),
        review_label=repo.get("label") is not None,
        bugbot_unavailable=any(
            lg == BUGBOT_BOT and BUGBOT_BILLING in body for lg, body in authored
        ),
        auto_reviewers=tuple(sorted(logins.intersection(AUTO_REVIEWERS))),
    )


def parse_pull(payload: dict) -> PullState:
    pr = payload["data"]["repository"]["pullRequest"]
    return PullState(
        open=pr["state"] == "OPEN",
        author=(pr.get("author") or {}).get("login") or "",
        labels=tuple(n["name"] for n in pr["labels"]["nodes"]),
        comments=tuple(_authored(pr["comments"]["nodes"])),
        claude_notice=any(
            _is_notice(lg, b) for lg, b in _authored(pr["reviews"]["nodes"])
        ),
    )


def subscribed(pull: PullState, account: str) -> bool:
    return any(
        login == account and body.strip().lower().startswith(CLAUDE_TRIGGER)
        for login, body in pull.comments
    )


def plan_actions(profile: Profile, pull: PullState, account: str) -> tuple[Action, ...]:
    """The requests still missing on this pull request."""
    comment = (profile.claude_manual or pull.claude_notice) and not subscribed(
        pull, account
    )
    label = profile.review_label and REVIEW_LABEL not in pull.labels
    return tuple(
        action
        for wanted, action in (
            (comment, Action(ActionKind.COMMENT, CLAUDE_TRIGGER)),
            (label, Action(ActionKind.LABEL, REVIEW_LABEL)),
        )
        if wanted
    )


def _graphql(runner: Runner, token: str, query: str, fields: dict[str, str]) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in fields.items():
        args = [*args, "-F" if key == "number" else "-f", f"{key}={value}"]
    try:
        return json.loads(runner(args, token))
    except json.JSONDecodeError as exc:
        raise GhError(f"unreadable GraphQL response: {exc}") from exc


def fetch_pull(runner: Runner, token: str, target: Target) -> PullState:
    fields = {"owner": target.owner, "name": target.name, "number": str(target.number)}
    return parse_pull(_graphql(runner, token, PULL_QUERY, fields))


def _read_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        json.dump(data, handle)
    os.replace(handle.name, path)


def load_profile(
    runner: Runner, token: str, target: Target, cache_path: Path, now: float
) -> Profile:
    """The repository profile, from a cache younger than the TTL or from GitHub."""
    cache = _read_cache(cache_path)
    entry = cache.get(target.slug)
    if isinstance(entry, dict) and now - entry.get("at", 0) < PROFILE_TTL_SECONDS:
        stored = entry["profile"]
        return Profile(**{**stored, "auto_reviewers": tuple(stored["auto_reviewers"])})
    fields = {"owner": target.owner, "name": target.name, "label": REVIEW_LABEL}
    profile = build_profile(_graphql(runner, token, PROFILE_QUERY, fields))
    _write_cache(
        cache_path, {**cache, target.slug: {"at": now, "profile": asdict(profile)}}
    )
    return profile


def apply_action(runner: Runner, token: str, target: Target, action: Action) -> None:
    base = f"repos/{target.slug}/issues/{target.number}"
    if action.kind is ActionKind.COMMENT:
        runner(
            ["api", f"{base}/comments", "-X", "POST", "-f", f"body={action.value}"],
            token,
        )
    else:
        runner(
            ["api", f"{base}/labels", "-X", "POST", "-f", f"labels[]={action.value}"],
            token,
        )


def describe(
    target: Target, profile: Profile, actions: tuple[Action, ...], dry_run: bool
) -> str:
    """One line naming what was requested and what needs nothing."""
    kinds = {a.kind for a in actions}
    verb = ("would post", "would add label") if dry_run else ("posted", "added label")
    parts = [
        f"{verb[0]} `{CLAUDE_TRIGGER}`" if ActionKind.COMMENT in kinds else "",
        "claude subscribed"
        if profile.claude_manual and ActionKind.COMMENT not in kinds
        else "",
        f"{verb[1]} `{REVIEW_LABEL}`" if ActionKind.LABEL in kinds else "",
        f"label `{REVIEW_LABEL}` present"
        if profile.review_label and ActionKind.LABEL not in kinds
        else "",
        f"auto {', '.join(profile.auto_reviewers)}" if profile.auto_reviewers else "",
        "bugbot unavailable (billing)" if profile.bugbot_unavailable else "",
    ]
    detail = ", ".join(p for p in parts if p) or "no AI reviewer configured"
    return f"ai-review: {target.slug}#{target.number} {detail}"


def request_reviews(
    target: Target,
    *,
    account: str,
    token: str,
    runner: Runner = run_gh,
    cache_path: Path = CACHE_PATH,
    now: float,
    dry_run: bool = False,
) -> str:
    """Request every missing review; empty when the PR is not my open PR."""
    pull = fetch_pull(runner, token, target)
    if not pull.open or pull.author != account:
        return ""
    profile = load_profile(runner, token, target, cache_path, now)
    effective = Profile(
        claude_manual=profile.claude_manual or pull.claude_notice,
        review_label=profile.review_label,
        bugbot_unavailable=profile.bugbot_unavailable,
        auto_reviewers=profile.auto_reviewers,
    )
    actions = plan_actions(effective, pull, account)
    for action in () if dry_run else actions:
        apply_action(runner, token, target, action)
    return describe(target, effective, actions, dry_run)


def parse_remote(
    url: str, resolve_host: Callable[[str], str] = str
) -> tuple[str, str] | None:
    """Owner and name of a GitHub remote; SSH aliases resolve through `resolve_host`."""
    match = REMOTE.search(url.strip())
    if not match or resolve_host(match.group(1)) != GITHUB_HOST:
        return None
    return match.group(2), match.group(3)


def pr_urls(text: str) -> tuple[Target, ...]:
    return tuple(
        Target(m.group(1), m.group(2), int(m.group(3))) for m in PR_URL.finditer(text)
    )

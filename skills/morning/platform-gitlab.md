# GitLab adapter

Substitutes the GitLab API surface into the phases of [`SKILL.md`](SKILL.md). The classification taxonomy, the age tiers, the consent model, and the merge prohibition are identical across platforms and are not restated here.

## Authentication probe, run first

```bash
glab auth status
```

No authenticated instance means this adapter reports one line and stops:

```
GitLab: no authenticated instance. Skipped.
```

Never present a skipped platform as clean. "Nothing waiting on GitLab" and "GitLab was not checked" are different statements and only one of them is true.

As of the last measurement on this machine, no GitLab instance is authenticated, so this path has not been exercised against a live instance. `glab auth login` is interactive and is blocked by [`glab-token-guard.py`](../../hooks/glab-token-guard.py), so the user runs it directly.

## Token resolution

Both variables are mandatory on every call, per [`multi-account-cli.md`](../../standards/multi-account-cli.md):

```bash
GITLAB_TOKEN=$(glab auth token --hostname <host>) GITLAB_HOST=<host> glab mr list
```

`GITLAB_HOST` has no safe default here. A self-managed instance and gitlab.com are different accounts with different work.

## Phase 1 query map

| GitHub query | GitLab equivalent |
|---|---|
| `gh search prs --review-requested=@me` | `glab mr list --reviewer=@me --state=opened` |
| `gh search prs --author=@me` | `glab mr list --author=@me --state=opened` |
| `gh search issues --assignee=@me` | `glab issue list --assignee=@me --state=opened` |
| `gh search issues --mentions=@me` | `glab api "/issues?scope=all&search=@<username>&state=opened"` |
| `gh api /notifications` | `glab api "/todos?state=pending"` |

The todos endpoint is the closest analogue to the notifications read and carries the same weight. GitLab routes an approval request through a todo, and a merge request assigned to a group rather than a person appears there and nowhere else.

## Merge state

GitLab exposes `detailed_merge_status` on the merge request object rather than the two-field GitHub pair:

```bash
GITLAB_TOKEN=$T GITLAB_HOST=$H glab api "/projects/:id/merge_requests/:iid" \
  --jq '{detailed_merge_status, has_conflicts, draft, blocking_discussions_resolved}'
```

Unlike GitHub, this value is computed eagerly, so the second poll that GitHub requires is unnecessary. `blocking_discussions_resolved` has no GitHub equivalent and belongs in the `blocked-on-me` decision: an unresolved discussion on my own merge request is a reply I owe.

## Branch update

```bash
GITLAB_TOKEN=$T GITLAB_HOST=$H glab mr rebase <iid>
```

GitLab's rebase runs server-side and does not force-push from the local checkout, so the objection that rules out `gh pr update-branch --rebase` does not apply. The branch-update budget still does, because a rebase triggers a pipeline exactly as a GitHub update does.

## Blocked commands

`glab mr merge` in every form is refused while the session lock is live, along with the REST equivalent `PUT /projects/:id/merge_requests/:iid/merge`. Both are covered by [`pr-merge-blocker.py`](../../hooks/pr-merge-blocker.py).

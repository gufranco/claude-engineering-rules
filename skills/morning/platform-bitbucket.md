# Bitbucket Cloud adapter

Substitutes the Bitbucket Cloud API surface into the phases of [`SKILL.md`](SKILL.md). The classification taxonomy, the age tiers, the consent model, and the merge prohibition are identical across platforms and are not restated here.

## Authentication probe, run first

Bitbucket ships no first-party CLI comparable to `gh` or `glab`, so the probe is a credential check rather than a status command:

```bash
test -n "$BITBUCKET_TOKEN" || test -n "$BITBUCKET_APP_PASSWORD"
```

Absent credentials mean this adapter reports one line and stops:

```
Bitbucket: no credentials configured. Skipped.
```

Never present a skipped platform as clean.

As of the last measurement on this machine, no Bitbucket credentials are configured and no CLI is installed, so this path has not been exercised against a live workspace.

## Token resolution

Two schemes, in preference order. Repository access tokens are scoped to one repository and are the safer choice:

```bash
curl -sS -H "Authorization: Bearer ${BITBUCKET_TOKEN}" \
  "https://api.bitbucket.org/2.0/..."
```

App passwords are the fallback and are workspace-wide, so they carry a larger blast radius:

```bash
curl -sS -u "${BITBUCKET_USERNAME}:${BITBUCKET_APP_PASSWORD}" \
  "https://api.bitbucket.org/2.0/..."
```

Never place a token in a URL. Query-string credentials land in shell history, in proxy logs, and in any error message that echoes the request.

## Phase 1 query map

Bitbucket has no cross-workspace search comparable to the GitHub search API, so discovery enumerates workspaces first, then repositories, then pull requests. This is the most expensive adapter and the one most likely to need pagination limits.

| GitHub query | Bitbucket equivalent |
|---|---|
| Enumerate accounts | `GET /2.0/workspaces?role=member` |
| Enumerate repositories | `GET /2.0/repositories/{workspace}?role=contributor` |
| `--review-requested=@me` | `GET /2.0/pullrequests/{selected_user}` then filter on `reviewers` |
| `--author=@me` | `GET /2.0/pullrequests/{selected_user}?state=OPEN` |
| `--assignee=@me` on issues | `GET /2.0/repositories/{workspace}/{repo}/issues?q=assignee.uuid="{uuid}"` |
| `/notifications` | No equivalent. Bitbucket exposes no notification inbox through the API |

The missing notification endpoint is a real coverage gap, not an omission. A pull request routed to a group rather than to a person may not surface. Say so in the report rather than implying full coverage.

Issue tracking is disabled on most Bitbucket repositories. A 404 on the issues endpoint means the tracker is off, which is not an error and is not reported as one.

## Merge state

```bash
curl -sS -H "Authorization: Bearer ${BITBUCKET_TOKEN}" \
  "https://api.bitbucket.org/2.0/repositories/{workspace}/{repo}/pullrequests/{id}" \
  | jq '{state, task_count, close_source_branch, merge_commit}'
```

Bitbucket exposes no direct equivalent of `mergeStateStatus`. Conflict detection requires the diff endpoint, which is why conflict state on this platform is resolved in Phase 4 for selected items rather than during discovery.

## Branch update

No server-side equivalent of `gh pr update-branch` exists. The update is local, and it pushes:

```bash
git fetch origin && git merge origin/<base> && git push origin <head>
```

The branch-update budget applies unchanged, and the local merge is the reason [`pr-merge-blocker.py`](../../hooks/pr-merge-blocker.py) deliberately leaves `git merge` alone.

## Blocked commands

`POST /2.0/repositories/{workspace}/{repo}/pullrequests/{id}/merge` is refused while the session lock is live, in every client form including `curl`. Covered by [`pr-merge-blocker.py`](../../hooks/pr-merge-blocker.py).

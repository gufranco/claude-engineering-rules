# Bitbucket Platform Support

Reference for `/respond` when the detected platform is Bitbucket Cloud. The workflow is identical to GitHub. The API surface differs and Bitbucket lacks a first-party CLI, so all interactions go through `curl` or `bb`, a community CLI.

## Status

Bitbucket support is light. The lack of a first-party CLI and the absence of a thread-resolution concept similar to GitHub mean some workflow steps require manual confirmation. The skill detects Bitbucket, switches to REST mode, and surfaces the limitations to the user.

## Detection

| Remote URL pattern | Platform |
|--------------------|----------|
| `bitbucket.org`, `*.bitbucket.org`, `git@bitbucket.org:` | Bitbucket Cloud |
| Self-hosted Bitbucket Server (Data Center) | Out of scope for this skill |

## Authentication

Bitbucket Cloud uses app passwords or workspace access tokens. The skill expects either `BITBUCKET_TOKEN` or `BITBUCKET_APP_PASSWORD` plus `BITBUCKET_USERNAME` to be set in the environment.

```bash
# App-password form
curl -u "$BITBUCKET_USERNAME:$BITBUCKET_APP_PASSWORD" "https://api.bitbucket.org/2.0/..."

# Token form (preferred for fine-grained scopes)
curl -H "Authorization: Bearer $BITBUCKET_TOKEN" "https://api.bitbucket.org/2.0/..."
```

The skill never invents credentials. If neither auth pair is present, it stops Phase 1 with an error pointing the user to `bitbucket.org/account/settings/app-passwords` or to the workspace token settings.

## REST API Surface

| Concern | Endpoint |
|---------|----------|
| Find PR for current branch | `GET /2.0/repositories/{workspace}/{repo}/pullrequests?q=source.branch.name="<branch>"` |
| Get PR detail | `GET /2.0/repositories/{workspace}/{repo}/pullrequests/{id}` |
| List inline comments | `GET /2.0/repositories/{workspace}/{repo}/pullrequests/{id}/comments` |
| Get one comment | `GET /2.0/repositories/{workspace}/{repo}/pullrequests/{id}/comments/{cid}` |
| Reply to an inline comment | `POST /2.0/repositories/{workspace}/{repo}/pullrequests/{id}/comments` with `parent.id` set |
| PR-level comment | Same endpoint without `parent.id` |
| Re-request review | `PUT /2.0/repositories/{workspace}/{repo}/pullrequests/{id}` with the `reviewers` array |

## Phase 2 Fetch on Bitbucket

```bash
curl -s -u "$BITBUCKET_USERNAME:$BITBUCKET_APP_PASSWORD" \
  "https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>/pullrequests/<id>/comments?pagelen=100" \
  > /tmp/respond-fetch-<id>.json
```

The response paginates via `next` URL. The skill follows pagination and concatenates pages until exhausted.

Filter rules:

- Drop comments where `deleted == true`.
- Group by `inline.path` and `inline.to` line to reconstruct thread structure. Bitbucket does not return explicit thread IDs; replies use `parent.id`.
- Apply the `--humans-only` filter by checking `user.account_id` against any known bot accounts in the workspace. Bitbucket does not surface a `type` field per user.

### AI Bot Detection on Bitbucket

Bitbucket has no convention like GitHub's `[bot]` suffix. The skill maintains a per-workspace allowlist of bot account UUIDs in `~/.config/respond/bitbucket-bots.json`. If the file is absent, every comment is treated as human.

## Resolve Concept

**Bitbucket Cloud does not have a "resolve thread" concept.** A comment can be `deleted`, `replied to`, or left as is. The skill handles this by:

1. Posting a reply with the action taken or the reason for dismissal.
2. Optionally setting a custom marker in the reply body, like a leading `RESOLVED:` token, so future readers can scan for closed threads.
3. Never deleting the original comment.

When `/respond` runs on Bitbucket and the user picks the `resolve` decision, the skill warns: "Bitbucket has no resolve action. Posting the reply only." The user can opt to add the `RESOLVED:` prefix via `--bitbucket-resolved-marker`.

## Phase 6 Step 5 Reply on Bitbucket

```bash
cat <<'PAYLOAD' > /tmp/respond-reply-<comment-id>.json
{
  "content": {
    "raw": "<draft reply body, includes the fix SHA>"
  },
  "parent": { "id": <parent-comment-id> }
}
PAYLOAD

curl -s -u "$BITBUCKET_USERNAME:$BITBUCKET_APP_PASSWORD" \
  -X POST \
  -H "Content-Type: application/json" \
  --data @/tmp/respond-reply-<comment-id>.json \
  "https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>/pullrequests/<id>/comments"
```

## Phase 6 Step 7 Re-request Review on Bitbucket

```bash
cat <<'PAYLOAD' > /tmp/respond-reviewers.json
{
  "reviewers": [
    { "uuid": "{<reviewer-uuid-1>}" },
    { "uuid": "{<reviewer-uuid-2>}" }
  ]
}
PAYLOAD

curl -s -u "$BITBUCKET_USERNAME:$BITBUCKET_APP_PASSWORD" \
  -X PUT \
  -H "Content-Type: application/json" \
  --data @/tmp/respond-reviewers.json \
  "https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>/pullrequests/<id>"
```

The `reviewers` array replaces the entire reviewer list. The skill fetches the current list, adds the requested users if missing, and PUTs the union.

## Differences from GitHub to Document in the Reply

| GitHub term | Bitbucket term |
|-------------|----------------|
| Pull Request | Pull Request |
| Review thread | Comment thread (no native concept) |
| Review comment | Inline comment |
| Reply chain | Comments with `parent.id` |
| `resolve thread` | No equivalent; reply is the closure signal |
| `re-request review` | PUT the PR with the reviewers array |
| `dismiss review` | No equivalent |

## Limitations vs GitHub

| Concern | Bitbucket limitation |
|---------|---------------------|
| Thread resolution | No native concept. Reply is the closure signal |
| Bot detection | No `[bot]` suffix convention. Per-workspace allowlist required |
| Pending review batching | No native concept. Comments post one at a time |
| Suggestion blocks | Bitbucket renders fenced code blocks but has no native "apply suggestion" button |
| First-party CLI | None. The skill uses `curl` with the REST API |

## Recommendation

For projects where Bitbucket usage is regular, consider migrating PR review workflows to GitHub or GitLab if feasible. Bitbucket's review API is older and the absence of a thread-resolution concept makes it the weakest of the three platforms for this kind of structured workflow. `/respond` supports Bitbucket but cannot deliver the same level of automation.

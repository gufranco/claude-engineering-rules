# GitLab Platform Support

Reference for `/respond` when the detected platform is GitLab. The workflow is identical to GitHub. Only the API surface differs.

## Detection

Platform is detected from the remote URL during Phase 1.

| Remote URL pattern | Platform |
|--------------------|----------|
| `github.com`, `*.github.com`, `git@github.com:` | GitHub |
| `gitlab.com`, `*.gitlab.com`, `git@gitlab.com:`, self-hosted GitLab via remote URL | GitLab |

The skill switches the CLI tool and the API endpoints accordingly. Account safety follows [`../../standards/multi-account-cli.md`](../../standards/multi-account-cli.md). For GitLab, the equivalent of `GH_TOKEN` is `GITLAB_TOKEN`, set via `GITLAB_TOKEN=$(glab auth token --hostname gitlab.com)`.

## glab CLI Surface

| Concern | Command |
|---------|---------|
| Find MR for current branch | `glab mr view --json url,iid,state,headRefName,baseRefName,author` |
| List discussions and notes | `glab api projects/:id/merge_requests/:iid/discussions` |
| Add an MR-level comment | `glab mr note <iid> --message "..."` |
| Reply to a discussion | `glab api projects/:id/merge_requests/:iid/discussions/<discussion_id>/notes -X POST --field body=...` |
| Resolve a discussion | `glab api projects/:id/merge_requests/:iid/discussions/<discussion_id> -X PUT --field resolved=true` |
| Unresolve a discussion | `glab api projects/:id/merge_requests/:iid/discussions/<discussion_id> -X PUT --field resolved=false` |
| Re-request review | `glab api projects/:id/merge_requests/:iid -X PUT --field reviewer_ids=...` |

GitLab does not need a GraphQL query for thread state. The REST endpoint returns `resolved` and `resolvable` on each discussion node, and the per-note `system: true` flag distinguishes bot-generated system notes from human comments.

## Phase 2 Fetch on GitLab

Replace the GraphQL block from SKILL.md Phase 2 with the REST equivalent.

```bash
GITLAB_TOKEN=$(glab auth token --hostname <host>) glab api \
  "projects/$(printf '%s' '<group>/<project>' | python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.stdin.read(), safe=\"\"))')/merge_requests/<iid>/discussions" \
  --paginate
```

Filter rules:

- Drop discussions where every note has `resolved == true`.
- Drop discussions where every note has `system == true`. System notes are auto-generated activity entries, not review comments.
- Apply the `--humans-only` filter by checking each first note's `author.username` against the AI bot allowlist below.

### AI Bot Allowlist on GitLab

| Tool | Common login pattern |
|------|---------------------|
| GitLab Duo | `gitlab-duo` or the project's configured Duo username |
| CodeRabbit on GitLab | `coderabbit` or `coderabbitai` |
| Sourcery | `sourcery-bot` |
| Greptile | `greptile-app` |

Auxiliary bots: `ggshield-bot`, `gitlab-dependabot`, `gitlab-renovate`, `pipeline-bot`. Skip these in `/respond` by default.

## Phase 6 Step 5 Reply on GitLab

For inline replies in a discussion thread:

```bash
cat <<'PAYLOAD' > /tmp/respond-reply-<discussion-id>.json
{
  "body": "<draft reply body, includes the fix SHA>"
}
PAYLOAD

GITLAB_TOKEN=$(glab auth token --hostname <host>) glab api \
  "projects/<encoded-project-path>/merge_requests/<iid>/discussions/<discussion-id>/notes" \
  -X POST \
  --input /tmp/respond-reply-<discussion-id>.json
```

For an MR-level summary reply:

```bash
GITLAB_TOKEN=$(glab auth token --hostname <host>) glab mr note <iid> \
  --message-file /tmp/respond-summary.md
```

## Phase 6 Step 6 Resolve on GitLab

```bash
GITLAB_TOKEN=$(glab auth token --hostname <host>) glab api \
  "projects/<encoded-project-path>/merge_requests/<iid>/discussions/<discussion-id>" \
  -X PUT \
  --field resolved=true
```

GitLab discussions support resolve and unresolve via the same endpoint with `resolved=false`. The `bulk-resolve-blocker.py` hook recognizes the GitLab pattern too: any loop iterating over discussion IDs with `resolved=true` in a `glab api ... -X PUT` is flagged.

## Phase 6 Step 7 Re-request Review on GitLab

GitLab uses `reviewer_ids` rather than reviewer usernames. The skill resolves usernames to IDs first.

```bash
# Step 1: resolve usernames to IDs
for user in alice bob; do
  GITLAB_TOKEN=$(glab auth token --hostname <host>) glab api "users?username=$user" --jq '.[0].id'
done

# Step 2: PUT the MR with the resolved IDs
GITLAB_TOKEN=$(glab auth token --hostname <host>) glab api \
  "projects/<encoded-project-path>/merge_requests/<iid>" \
  -X PUT \
  --field reviewer_ids[]=<id1> --field reviewer_ids[]=<id2>
```

Pair the re-request with an MR-level comment that uses `PTAL` and summarizes the changes since the last round, same convention as GitHub.

## Differences from GitHub to Document in the Reply

| GitHub term | GitLab term |
|-------------|-------------|
| Pull Request | Merge Request |
| Review thread | Discussion |
| Review comment | Note |
| `outdated` flag | `resolvable` flag on the discussion, plus `position.line_range` change-tracking |
| `request review` | `set reviewers` via `reviewer_ids` |
| `dismiss review` | No exact equivalent; an Approval can be revoked via the API |

When `/respond` drafts a reply for a GitLab discussion, the reply text avoids GitHub-specific vocabulary like "PR" and uses "MR" when speaking to the reviewer. The intent taxonomy from Conventional Comments is identical across platforms.

## Resolved Concept on GitLab

GitLab distinguishes `resolvable` from `resolved`:

- `resolvable == true`: the discussion can be resolved or unresolved.
- `resolvable == false`: system or activity discussion, no resolve UI.
- `resolved == true`: the discussion is in the resolved state.

The skill treats `resolvable == false` discussions the same way it treats GitHub `isOutdated == true`: out of scope for the workflow.

## Project Path Encoding

GitLab API endpoints require the project path to be URL-encoded. The skill encodes the path once per invocation and reuses the encoded string. Example:

```bash
PROJECT_PATH=$(printf '%s' 'group/subgroup/project' | python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.stdin.read(), safe=""))')
```

Self-hosted GitLab instances need an explicit `--hostname` flag on every `glab` invocation. The skill detects the hostname from the remote URL during Phase 1.

## Limitations vs GitHub

| Concern | GitLab limitation |
|---------|------------------|
| Per-comment severity labels | Not native. The skill applies the Conventional Comments prefix in the body text instead |
| Pending review batching | GitLab does not have GitHub's "pending review" concept. The skill posts each reply as a discrete note |
| `dismiss review` | Approvals can be revoked but the API path differs per instance configuration. The skill never dismisses approvals |
| `re-request specific reviewer` | The `reviewer_ids` PUT replaces the entire reviewer list. The skill fetches the current list, adds the requested users if missing, and PUTs the union |

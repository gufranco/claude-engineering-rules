# PR Comment Channels

## Core Rule

Every comment on a pull request, of every type, that is not in a terminal state is in scope for any skill that reads or responds to review feedback. Inline diff comments are one channel among four on GitHub. Treating them as the whole set is the single most common failure mode in this area: a reviewer posts a blocking concern in the conversation box, the skill sweeps only `reviewThreads`, and reports "nothing to respond to" while the concern sits unanswered.

A skill must never report a PR as clean while any non-terminal comment in any channel remains unhandled.

## Why This Rule Exists

An earlier session missed a P0 deadlock report because it was posted as a PR-level conversation comment rather than an inline thread. The fetch query only asked for `reviewThreads`. The comment was invisible to the workflow, and the skill reported the PR as having no open feedback.

The failure is structural, not incidental. `reviewThreads` is the only channel with a native `isResolved` flag, so it is the only channel that has an obvious "is this handled?" signal. The other three channels have no resolve concept, which makes them easy to omit and easy to misclassify once fetched. This standard names all four channels and defines a terminal state for each so the omission cannot recur.

## Channel Inventory: GitHub

Verified against the live GraphQL schema. Four channels carry comments on a pull request.

| Channel | GraphQL field | Native resolve | What lives here |
|---------|---------------|----------------|-----------------|
| Inline review threads | `pullRequest.reviewThreads` | Yes, `isResolved` | Line-level and file-level diff comments. `subjectType` is `LINE` or `FILE` |
| Review summary bodies | `pullRequest.reviews` | No | The body text submitted with an `APPROVED`, `CHANGES_REQUESTED`, or `COMMENTED` review. Most AI reviewers post their summary and their highest-severity findings here |
| PR conversation comments | `pullRequest.comments` | No | The bottom "Add a comment" box. Issue comments in REST terms. Where humans post blocking concerns that are not tied to a line |
| Commit comments | `pullRequest.timelineItems`, item type `PullRequestCommitCommentThread` | No | Comments attached to a single commit inside the PR. Reachable only through `timelineItems` |

The fourth channel is invisible to every query that asks only for `reviewThreads`, `reviews`, and `comments`. It requires an explicit `itemTypes` filter on `timelineItems`.

### Canonical GitHub fetch

This query returns all four channels in one round trip. It is verified to execute against the live API.

```graphql
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          isCollapsed
          path
          line
          subjectType
          comments(first: 50) {
            nodes {
              databaseId
              author { login }
              authorAssociation
              body
              createdAt
              url
              isMinimized
              minimizedReason
            }
          }
        }
      }
      reviews(first: 100) {
        nodes {
          id
          databaseId
          author { login }
          body
          state
          submittedAt
          url
          isMinimized
          minimizedReason
        }
      }
      comments(first: 100) {
        nodes {
          id
          databaseId
          author { login }
          body
          createdAt
          url
          isMinimized
          minimizedReason
        }
      }
      timelineItems(first: 100, itemTypes: [PULL_REQUEST_COMMIT_COMMENT_THREAD]) {
        nodes {
          ... on PullRequestCommitCommentThread {
            path
            position
            commit { oid }
            comments(first: 50) {
              nodes {
                databaseId
                author { login }
                body
                createdAt
                url
                isMinimized
                minimizedReason
              }
            }
          }
        }
      }
    }
  }
}
```

Write the query to a temp file and invoke it with the account resolved per [`multi-account-cli.md`](multi-account-cli.md):

```bash
GH_TOKEN=$(gh auth token --user <account>) gh api graphql \
  -f query="$(cat /tmp/pr-channels-<pr>.graphql)" \
  -F owner=<owner> -F repo=<repo> -F pr=<number>
```

Paginate when any channel returns a full page. A PR with more than 100 review threads is rare but real, and a silently truncated fetch reintroduces the exact bug this standard exists to prevent.

## Channel Inventory: GitLab

| Channel | Endpoint | Native resolve | Notes |
|---------|----------|----------------|-------|
| Diff discussions | `projects/:id/merge_requests/:iid/discussions` | Yes | Notes of type `DiffNote`. `resolvable: true` |
| Non-diff discussions | Same endpoint | Yes | Notes of type `DiscussionNote`, posted on the MR overview. Resolvable, contrary to a common assumption |
| Individual notes | Same endpoint | No | `individual_note: true`. Standalone MR-level comments. Never carry a `resolved` field |
| System notes | Same endpoint | Not applicable | `system: true`. Automated activity entries. Out of scope |
| Commit discussions | `projects/:id/repository/commits/:sha/discussions` | No | Separate endpoint. Not returned by the MR discussions endpoint |

`resolvable == false` must never be used as a drop filter. It is true for system notes, which are correctly dropped, and it is also true for individual notes, which are actionable MR-level comments. Filter on `system == true` to drop automation, then treat every remaining discussion as in scope.

## Channel Inventory: Bitbucket Cloud

| Channel | Endpoint | Native resolve | Notes |
|---------|----------|----------------|-------|
| Inline comments | `/2.0/repositories/{workspace}/{repo}/pullrequests/{id}/comments` | Yes | Carry an `inline` object with `path` and `to` |
| PR-level comments | Same endpoint | Yes | No `inline` object. Distinguished by its absence |
| Commit comments | `/2.0/repositories/{workspace}/{repo}/commit/{sha}/comments` | No | Separate endpoint |

Bitbucket Cloud does support comment resolution. The comment object carries a `resolution` field, and the endpoints are:

```bash
# Resolve
curl -s -X POST -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>/pullrequests/<id>/comments/<cid>/resolve"

# Unresolve
curl -s -X DELETE -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  "https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>/pullrequests/<id>/comments/<cid>/resolve"
```

A comment with `resolution` set to a non-null value is resolved. A comment with `pending: true` is an unpublished draft and is out of scope until published.

## Terminal States

"Unresolved" needs a definition per channel, because only one channel has a resolve flag. A comment is terminal, meaning out of scope, when any row below matches. Everything else is in scope.

| Terminal state | Detection | Applies to |
|----------------|-----------|------------|
| Resolved | `isResolved == true` on GitHub, `resolved == true` on GitLab, `resolution != null` on Bitbucket | Channels with native resolve |
| Minimized | `isMinimized == true` on GitHub | All four GitHub channels |
| Deleted | `deleted == true` on Bitbucket, node absent on GitHub and GitLab | All |
| Automated activity | `system == true` on GitLab | GitLab discussions |
| Unpublished draft | `pending: true` on Bitbucket, `state == PENDING` on a GitHub review | Bitbucket comments, GitHub reviews |
| Authored by the running account | Author login matches the resolved account, and no later reply from another party | All |
| Already answered | The running account posted a reply in the same channel after the comment's `createdAt`, and that reply addresses it | Channels without native resolve |
| Auto-generated marker | Body begins with a tracker or bot marker such as an HTML comment used for linkbacks or summaries | PR-level comments |

GitHub's `minimizedReason` is one of `SPAM`, `ABUSE`, `OFF_TOPIC`, `OUTDATED`, `DUPLICATE`, `RESOLVED`, `LOW_QUALITY`. Any of them marks the comment as handled by a human decision. Minimizing is the closest thing the three non-resolvable GitHub channels have to a resolve action, and it must be honored.

### Outdated is not terminal

`isOutdated == true` on GitHub and a changed `position` on GitLab mean the cited line moved, not that the concern was addressed. A comment can be outdated and still name a live bug. Never drop on outdated alone. The same applies to `isCollapsed`, which is a display hint rather than a decision.

## Handling Channels Without Native Resolve

Three of the four GitHub channels cannot be resolved through the API. The workflow closes them differently.

| Channel | How to reply | How to close |
|---------|-------------|--------------|
| Inline review thread | `POST repos/<o>/<r>/pulls/<pr>/comments/<comment-id>/replies` | `resolveReviewThread` GraphQL mutation |
| Review summary body | `gh pr comment <pr> --body-file <file>`, quoting the point being answered | Minimize the review when the reply fully settles it, otherwise leave it to the reviewer |
| PR conversation comment | `gh pr comment <pr> --body-file <file>` | No resolve action. The reply is the closure signal |
| Commit comment | `POST repos/<o>/<r>/comments/<comment-id>/replies` is not available. Reply with a PR-level comment that quotes the commit and the point | No resolve action. The reply is the closure signal |

For channels with no resolve, the reply is the audit trail. A skill must post a reply rather than silently treating the comment as handled, because there is no state on the platform to record the decision.

## Completeness Cross-Check

After fetching, before reporting status, run this check. It is the guard that turns the rule into something verifiable.

1. Sort every comment from every channel by `createdAt` descending, into one list.
2. Drop the terminal ones per the table above.
3. If the list is non-empty, the PR has open feedback. Report it, broken out by channel.
4. If the most recent non-terminal item is newer than the running account's most recent reply anywhere on the PR, surface it explicitly, even when every inline thread is resolved.
5. Report per-channel counts, never a single total. A total of zero hides which channels were actually queried.

Step 5 matters: a report of "0 open threads" is ambiguous between "all four channels are clean" and "I only looked at one channel". Per-channel counts make an omission visible in the output.

## Cross-References

- [`code-review.md`](code-review.md): review conduct and the Conventional Comments taxonomy
- [`multi-account-cli.md`](multi-account-cli.md): the account-resolution pattern every `gh`, `glab`, and `curl` call follows
- [`../skills/respond/SKILL.md`](../skills/respond/SKILL.md): the receive-side workflow that consumes this standard
- [`../skills/ship/SKILL.md`](../skills/ship/SKILL.md): the pipeline loop whose bot sweep consumes this standard
- [`../skills/review/SKILL.md`](../skills/review/SKILL.md): reads existing feedback before adding more

## Sources

Verified 2026-07-16 against live APIs rather than documentation prose.

- GitHub GraphQL schema, introspected via `gh api graphql` for `PullRequest`, `PullRequestReview`, `PullRequestReviewThread`, `PullRequestTimelineItems`, `CommitComment`, and `ReportedContentClassifiers`.
- GitHub REST docs, <https://docs.github.com/en/rest/pulls/comments> and <https://docs.github.com/en/rest/commits/comments>, for the three-way distinction between review, issue, and commit comments.
- GitLab discussions API, <https://docs.gitlab.com/api/discussions/>, for `individual_note`, `resolvable`, `resolved`, and `system`.
- Bitbucket Cloud swagger, <https://api.bitbucket.org/swagger.json>, for the `resolve` endpoint pair and the `resolution` and `pending` fields.

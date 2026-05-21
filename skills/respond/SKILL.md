---
name: respond
description: Respond to incoming code review comments on a PR you authored. Fetches unresolved threads, classifies each by author and intent, verifies against the current code, drafts replies in a natural voice, applies code changes with local validation, posts replies, resolves threads, and monitors CI. Use when user says "respond to review", "address comments", "handle reviewer feedback", "reply to PR comments", "my PR has comments", or wants a structured pass over reviewer feedback. Do NOT use for performing a review (use /review), or for unattended AI bot thread handling (use /ship --pipeline).
sensitive: true
---
Receive-side counterpart to `/review`. Turns the loose, error-prone workflow of "respond to PR review comments" into a structured, validated pipeline. The seven phases take the user from "I see comments on my PR" to "every thread is replied to or resolved, code changes are validated and pushed, CI is green".

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/respond` | Full workflow on the current branch's PR |
| `/respond <PR>` | Same workflow targeting a specific PR number or URL |
| `/respond fetch` | Phase 1 to Phase 3 only. List threads with classification. No implementation, no posting |
| `/respond reply <thread-id>` | Reply to one specific thread. Skip the batch flow |
| `/respond resolve <thread-id>` | Resolve one specific thread. No reply |

If no subcommand is given, default to the full workflow.

## Arguments

| Flag | Effect |
|------|--------|
| No args | Use the current branch's PR |
| `<PR number or URL>` | Target that PR |
| `--humans-only` | Default. Skip threads whose first comment is from a bot |
| `--include-bots` | Include AI bot threads in the workflow |
| `--auto` | Execute the approved batch without per-batch confirmation. Requires `RESPOND_AUTO_ACK=1` env var to take effect |
| `--interactive` | Confirm per thread instead of per batch |
| `--filter <pattern>` | Filter threads by file path glob or author login |
| `--dry-run` | Run Phases 1 through 5, print the proposed actions, exit without executing |
| `--re-request` | Re-request review from the original reviewers after the batch ships |
| `--no-resolve` | Skip the resolution step |
| `--resolve-by <author\|reviewer>` | Resolution convention. Default `author`, opt-in `reviewer` |
| `--force-during-review` | Allow force-push even when an open CHANGES_REQUESTED review exists. Off by default |

## Phase 1: Discover PR

1. Run **in parallel**: `git remote get-url origin`, `git branch --show-current`, `git status --porcelain`.
2. Detect platform from the remote URL. Supported platforms: GitHub, GitLab, Bitbucket Cloud. The default workflow in this file documents GitHub. For GitLab specifics, read `platform-gitlab.md` and substitute the API surface. For Bitbucket Cloud, read `platform-bitbucket.md` and substitute. The classification taxonomy, reply templates, and bot triage rules are identical across platforms.
3. Resolve the platform account per `../../standards/multi-account-cli.md`. GitHub uses `GH_TOKEN=$(gh auth token --user <account>) gh ...`. GitLab uses `GITLAB_TOKEN=$(glab auth token --hostname <host>) glab ...`. Bitbucket uses `BITBUCKET_TOKEN` or `BITBUCKET_USERNAME`+`BITBUCKET_APP_PASSWORD` via `curl`.
4. Resolve the PR. If an argument is passed, parse it. Otherwise look up the PR for the current branch.

   ```bash
   GH_TOKEN=$(gh auth token --user <account>) gh pr view \
     --json number,url,state,headRefOid,headRefName,baseRefName,author,reviewRequests \
     --jq '{number, url, state, headRefOid, head: .headRefName, base: .baseRefName, author: .author.login, requested: [.reviewRequests[].requestedReviewer.login]}'
   ```

5. Validate. If PR is `CLOSED` or `MERGED`, ask before proceeding. If no PR is found and no argument is passed, stop.
6. Warn on uncommitted changes that conflict with the working tree the skill will modify.

## Phase 2: Fetch Threads

Use a single GraphQL query to pull all unresolved threads plus the review-level state.

```graphql
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          startLine
          diffSide
          comments(first: 50) {
            nodes {
              databaseId
              author { login, ... on User { name } }
              authorAssociation
              body
              createdAt
              url
            }
          }
        }
      }
      reviews(first: 100, states: [APPROVED, CHANGES_REQUESTED, COMMENTED]) {
        nodes {
          databaseId
          author { login }
          body
          state
          submittedAt
        }
      }
    }
  }
}
```

Invocation pattern. Write the query to `/tmp/respond-query-<pr>.graphql` and run:

```bash
GH_TOKEN=$(gh auth token --user <account>) gh api graphql \
  -f query="$(cat /tmp/respond-query-<pr>.graphql)" \
  -F owner=<owner> -F repo=<repo> -F pr=<number>
```

Filter rules.

- Drop threads with `isResolved == true`.
- Apply `--humans-only` filter unless `--include-bots` is set. The human filter keeps threads whose first comment is from `author.type == "User"` AND login is not in the AI bot allowlist.
- Group threads by file path, then sort by line number within file.
- Group reviews separately as summary-level entries.

AI bot allowlist for classification: `coderabbitai[bot]`, `copilot-pull-request-reviewer[bot]`, `greptile-apps[bot]`, `sourcery-ai[bot]`, `korbit-ai[bot]`, `cursor[bot]`, `qodo-merge-pro[bot]`, `bito-pr-review[bot]`, `gemini-code-assist[bot]`, `claude[bot]`, `tabnine-ai[bot]`. Auxiliary lint or dependency bots: `github-actions[bot]`, `dependabot[bot]`, `renovate[bot]`, `pre-commit-ci[bot]`, `lefthook[bot]`.

## Phase 3: Classify and Verify

For each thread, classify on three axes.

### Axis 1: Author type

| Value | Detection |
|-------|-----------|
| `human` | `author.type == "User"` AND login is not in the AI bot allowlist |
| `bot:ai` | `author.type == "Bot"` AND login matches the AI bot allowlist |
| `bot:lint` | `author.type == "Bot"` AND login matches an auxiliary lint or dependency bot |
| `bot:other` | `author.type == "Bot"` AND no other category matches |
| `self` | Author login matches the resolved account |

### Axis 2: Comment intent

Use the Conventional Comments taxonomy. When the reviewer used an explicit prefix like `nitpick:`, `suggestion:`, `issue:`, `question:`, `praise:`, `thought:`, `chore:`, or `todo:`, trust that prefix verbatim. Otherwise classify heuristically.

| Intent | Conventional Comments mapping | Keyword and structural signals |
|--------|------------------------------|--------------------------------|
| `issue:blocking-bug` | `issue (blocking)` | "this is broken", "will crash", "null pointer", "off-by-one", reproducer present |
| `issue:blocking-security` | `issue (security, blocking)` | "leak", "injection", "auth", "permission", "secret", "CVE", "credential" |
| `issue:blocking-correctness` | `issue (blocking)` | "wrong", "incorrect logic", "this returns", "should be" with a clear assertion |
| `issue:architectural` | `issue (non-blocking)` | "rethink", "different approach", "this whole pattern", "redesign" |
| `suggestion` | `suggestion` | "consider", "could", "what about", "alternatively" |
| `question` | `question` | Ends with `?`, "why did you", "how does this", "is this intentional" |
| `thought` | `thought` | Reflective, no requested action, "I wonder if", "musing" |
| `nitpick` | `nitpick` | Prefixed `nit:`, `nitpick:`, `style:`, very small scope |
| `praise` | `praise` | "nice", "good catch", "clean", no actionable content |
| `chore:out-of-scope` | `chore` | "separate PR", "follow-up", "out of scope" |
| `todo` | `todo` | "leave a TODO", reminder for the future, not for this PR |
| `clarification-request` | `question` | "what does this do", "can you explain", "I do not follow" |

### Axis 3: Action decision

Set by the verification step below.

| Decision | Meaning |
|----------|---------|
| `implement` | Comment is correct, apply the fix |
| `push-back` | Comment is incorrect, explain why |
| `clarify` | Need more info from reviewer before acting |
| `defer` | Valid but for a follow-up PR or ticket |
| `ack` | Acknowledge praise or info-only comment |
| `accept-with-modification` | Implement a variant of the suggestion |
| `conflict` | Two reviewers contradict on the same line. See Multi-Reviewer Conflict Resolution |

For `issue:blocking-*` intents, the decision space is restricted to `implement`, `push-back`, `clarify`. `defer` is forbidden.

### Verification step

For every thread classified as `issue:*`, `suggestion`, or `architectural`, read the cited file at the cited line, plus 50 lines of surrounding context. Verify against the current code, not against the code at the time the comment was posted.

| Check | Why |
|-------|-----|
| Does the cited code still exist? | If `isOutdated == true`, the comment may already be resolved by a later push |
| Does the cited code do what the reviewer claims? | False positives happen, especially with AI reviewers |
| Would the suggestion actually be better? | Apply the same criteria the `/review` skill uses |
| Are there hidden constraints the reviewer did not see, like tests, callers, or contracts? | Surfaces push-back cases with evidence |
| Can the bug be reproduced locally? | If not, the reply names the steps tried |

Output per thread: a classification record with author type, intent, decision, evidence, and a draft reply.

## Phase 4: Draft Strategy

For each thread, draft a reply and, when applicable, a code change. The reply follows the natural voice rules from `../../standards/code-review.md` and `../../rules/writing-precision.md`, plus the four communication principles below.

### Principle 1: Fix the code before explaining it

When a reviewer did not understand, the code is the first thing to change. Renaming a confusing variable, extracting a helper, or adding a code-level comment beats writing a thread reply that future readers will not see. Source: Google eng-practices "Handling reviewer comments", Tidyverse code review guide.

### Principle 2: Lead with reasoning when pushing back

Bare "I disagree" is a known failure mode. Use the Feedback Equation pattern: Observation, Impact, Request. State what the code does, what would change if you took the reviewer's path, and what you want from the reviewer next.

Example. Observation: "The current code uses `setTimeout` instead of `requestAnimationFrame`." Impact: "Switching to `requestAnimationFrame` would skip the ping when the tab is backgrounded, breaking the keep-alive contract documented in `docs/keepalive.md`." Request: "Want me to add a code comment explaining the constraint, or do you see a way to keep the behavior with a different API?"

### Principle 3: Switch to synchronous after two round trips

When a thread has cycled twice without convergence, propose a brief call. The skill does not initiate calls but tags the thread `synchronous-recommended` so the user can act on it.

### Principle 4: When you cannot reproduce, name the steps

"Couldn't reproduce" is a defensive wall. "Couldn't reproduce. Steps I tried: A, B, C. Did I miss something?" invites the reviewer to clarify.

### Reply templates

Full exemplars with good and bad counterparts live in `reply-templates.md`. The summary table covers the common intent-by-decision pairs.

| Intent x Decision | Template summary |
|-------------------|-------------------|
| `issue:blocking-bug` x `implement` | "You're right. Pushed `<SHA>`. <one-sentence on the fix>." Add a named regression test |
| `issue:blocking-bug` x `push-back` | Feedback Equation form. End with "Did I miss something?" |
| `issue:blocking-security` x `implement` | "You're right. Pushed `<SHA>` with <fix>. Will also <follow-up> in a separate change." File a ticket for the follow-up |
| `issue:blocking-correctness` x `clarify` | "Want to make sure I am understanding. <Restate reviewer's claim>. Is that right?" |
| `issue:architectural` x `push-back` | "Want to land this PR with the current approach. The redesign is worth a separate thread. <Reason>." |
| `suggestion` x `implement` | "Good call. Applied in `<SHA>`." Credit trailer for non-trivial suggestions |
| `suggestion` x `accept-with-modification` | "Took a variant in `<SHA>`. <Difference from the original>." |
| `suggestion` x `push-back` | "Considered that. Went with the current approach because <reason>. The alternative would <downside>." |
| `question` x `ack` | "<Direct answer>." If the answer reveals confusing code, fix the code instead |
| `clarification-request` x `ack` | "<Plain explanation>." If non-trivial, add a code comment |
| `nitpick` x `implement` | "Fixed in `<SHA>`." |
| `nitpick` x `push-back` | "Sticking with the current style for consistency with <other pattern>." |
| `chore:out-of-scope` x `defer` | "Filed as `<ticket-link>`. Out of scope for this PR." Never defer without a ticket |
| `todo` x `ack` | Add `TODO(debt):` code comment. Reply: "Added `TODO(debt)` at <file:line>" |
| `praise` x `ack` | Default: no reply. React with thumbs-up emoji on GitHub, silently resolve |
| AI bot x any | See "AI Bot Triage Tactics" below. Most bot threads end in `dismiss` |

Every template passes the no-internal-config-leakage check before posting.

### Code change planning

For `implement` and `accept-with-modification` decisions, draft the change at the line level. Record: the file path, the lines to modify, the new content, and the validation tests that must pass after.

For `issue:blocking-*` decisions, plan a named regression test like `it('rejects empty companyId per PR #4521')`. Apply when the bug has a specific reproducer, the fix is a one-line guard whose absence could regress invisibly, or the bug was filed by a user or downstream team. Skip when the regression would be loud, like a compile error or a type error.

## Phase 5: Present and Approve

Print a batched table to the terminal. One row per thread.

```
#  Author          File:Line              Intent                 Decision      Reply preview                 Code change
1  alice           src/auth.ts:42         issue:blocking-bug     implement     "You're right. Pushed..."     +12 -3 in src/auth.ts
2  bob             src/auth.ts:78         suggestion             push-back     "Considered that. Went..."    none
3  coderabbitai    src/orders.ts:120      nitpick                implement     "Fixed."                       +1 -1 in src/orders.ts
4  alice           README.md:5            question               ack           "The flow is described..."    none
5  carol           src/db.ts:200          issue:blocking-bug     conflict      flagged, see Conflict tab     held
```

If the batch exceeds 25 rows, paginate with `--filter` suggestions.

Prompt the user to approve the batch as a whole, edit a specific row, split into smaller batches, or abort. `--auto` plus the `RESPOND_AUTO_ACK=1` env var skips the prompt. `--interactive` shifts to per-row approval.

If `--dry-run`, stop here and exit.

## Phase 6: Execute Approved Batch

Order: code first, then reply, then resolve. Each step has its own checkpoint.

### Step 1: Apply code changes

Each thread's change becomes its own commit. Commit message format: `fix(<scope>): <one-line description>`. Body includes `Refs: <comment URL>`. Credit trailers per "Commit Credit Conventions" below.

### Step 2: Run the local quality gate

In order. Show output for each. If any fails, stop and report.

| Step | Detection |
|------|-----------|
| Format | `prettier --check`, `black --check`, `gofmt -l`, `rustfmt --check`, depending on the project |
| Lint | `eslint`, `ruff`, `golangci-lint`, `clippy --deny warnings`, depending on the project |
| Type check | `tsc --noEmit`, `mypy --strict`, `pyright`, depending on the project |
| Test | The project's full suite, with coverage if scripted |
| Build | The project's build command |

Use the same detection logic as `/ship pr` step 4.

### Step 3: Push once at the end

After all commits land cleanly. Use `-u` if no upstream is set. Use `--force-with-lease` only if a rebase rewrote history. Never use `--force`. If an open CHANGES_REQUESTED review exists on the PR, the push hooks block force unless `--force-during-review` was passed.

### Step 4: Re-fetch threads

Confirm the latest SHA is on the PR and no new threads landed during execution.

### Step 5: Post replies via REST

For inline threads, write a JSON file to `/tmp/respond-reply-<thread-id>.json`. Single-quoted heredoc to prevent shell expansion.

```bash
cat <<'PAYLOAD' > /tmp/respond-reply-<thread-id>.json
{
  "body": "<draft reply body, includes the fix SHA>"
}
PAYLOAD

GH_TOKEN=$(gh auth token --user <account>) gh api \
  repos/<owner>/<repo>/pulls/<pr>/comments/<comment-id>/replies \
  -X POST \
  --input /tmp/respond-reply-<thread-id>.json
```

For PR-level summary replies, post via:

```bash
GH_TOKEN=$(gh auth token --user <account>) gh pr comment <pr> \
  --body-file /tmp/respond-summary.md
```

### Step 6: Resolve threads via GraphQL

For each thread whose decision is `implement`, `push-back`, `defer`, `accept-with-modification`, or `ack`, post the reply first, then resolve. Threads with decision `clarify` stay open. Threads with decision `conflict` stay open until the conflicting reviewers align.

```bash
GH_TOKEN=$(gh auth token --user <account>) gh api graphql \
  -f query='mutation($threadId: ID!) {
    resolveReviewThread(input: { threadId: $threadId }) {
      thread { id, isResolved }
    }
  }' -F threadId=<thread-id>
```

One resolve per thread. The `bulk-resolve-blocker.py` hook enforces this.

### Step 7: Re-request review

If `--re-request` was passed.

```bash
GH_TOKEN=$(gh auth token --user <account>) gh api \
  repos/<owner>/<repo>/pulls/<pr>/requested_reviewers \
  -X POST \
  -f reviewers='["alice","bob"]'
```

Pair the re-request with a top-level PR comment that uses the `PTAL` shorthand and summarizes what changed since the last round.

### Step 8: Clean up

```bash
rm /tmp/respond-reply-*.json /tmp/respond-summary.md /tmp/respond-query-*.graphql
```

## Phase 7: Monitor and Close

After every push triggered by the batch, enter the Pipeline Monitoring loop from `/ship`. Reuse the same loop as a shared procedure. Loop until CI is green on the latest SHA AND no new threads have appeared since the last fetch. Bot threads that appear after the push are deferred to `/ship --pipeline` unless `--include-bots` was set.

Final output:

```
RESOLVED: 7 threads addressed on PR #1234.
  - 3 implemented (commits: a1b2c3d, e4f5g6h, i7j8k9l)
  - 2 pushed back with reasoning
  - 1 deferred to ticket TICKET-456
  - 1 acknowledged
  CI: 12 of 12 checks passed
  Re-requested review from: alice, bob
```

## Ticket Tracker Integration

For the `defer` decision, deferred items must include a ticket URL. The skill detects the project's tracker and offers to auto-file the ticket.

### Detection

| Tracker | Detection signal |
|---------|------------------|
| GitHub Issues | Default for GitHub repos. `gh repo view --json hasIssuesEnabled` returns true |
| Linear | `LINEAR_API_KEY` env var is set, or `.linear` directory exists, or `linear-config.yml` exists in the repo |
| Jira | `JIRA_API_TOKEN` env var is set, or `.jira.yml` exists, or the repo has a known Jira project mapping |
| GitLab Issues | Default for GitLab repos when issues are enabled. `glab api projects/:id --jq .issues_enabled` returns true |
| None detected | Skill prints a reminder and asks the user to file externally |

### Auto-File Helper

When the user approves a batch with `defer` decisions, the skill prompts:

```
3 deferred items in this batch:
  - "Extract auth middleware" (from alice's comment at src/auth.ts:42)
  - "Add E2E test for the migration" (from bob's comment at tests/migration.spec.ts:10)
  - "Bench the new query" (from carol's comment at src/db/orders.ts:78)

Tracker detected: GitHub Issues on <owner>/<repo>.
File all 3 as issues now? [y/n/select]
```

The user picks one of: `y` to file all, `n` to print a reminder only, `select` for per-item confirmation.

### GitHub Issues Auto-File

```bash
cat <<'PAYLOAD' > /tmp/respond-issue-<idx>.json
{
  "title": "<deferred item title>",
  "body": "Deferred from PR #<pr> review by <reviewer>.\n\nOriginal comment:\n<quoted comment>\n\nLink: <comment URL>",
  "labels": ["deferred-from-review"]
}
PAYLOAD

GH_TOKEN=$(gh auth token --user <account>) gh api \
  "repos/<owner>/<repo>/issues" \
  -X POST \
  --input /tmp/respond-issue-<idx>.json
```

### Linear Auto-File

```bash
curl -s \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d "{\"query\": \"mutation { issueCreate(input: { teamId: \\\"<team-id>\\\", title: \\\"<title>\\\", description: \\\"<body>\\\" }) { issue { url } } }\"}" \
  https://api.linear.app/graphql
```

The skill resolves `<team-id>` from `LINEAR_TEAM_ID` env var or by querying `teams` if only one team exists.

### Jira Auto-File

```bash
cat <<'PAYLOAD' > /tmp/respond-jira-<idx>.json
{
  "fields": {
    "project": { "key": "<JIRA_PROJECT_KEY>" },
    "summary": "<title>",
    "description": "<body>",
    "issuetype": { "name": "Task" }
  }
}
PAYLOAD

curl -s \
  -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST \
  --data @/tmp/respond-jira-<idx>.json \
  "https://<jira-host>/rest/api/3/issue"
```

The skill resolves `<JIRA_PROJECT_KEY>` from `JIRA_PROJECT_KEY` env var or from `.jira.yml`.

### GitLab Issues Auto-File

```bash
GITLAB_TOKEN=$(glab auth token --hostname <host>) glab api \
  "projects/<encoded-project-path>/issues" \
  -X POST \
  --field "title=<title>" \
  --field "description=<body>" \
  --field "labels=deferred-from-review"
```

### What the Reply Looks Like

After filing, the skill inserts the ticket URL into the draft reply for the deferred thread:

```
Filed as <ticket-url>. Out of scope for this PR.
```

If the user picks `n` to print a reminder only, the draft reply becomes:

```
Out of scope for this PR. I will file a follow-up ticket today.
```

The skill prints a reminder to the user's terminal listing the deferred items they need to track manually.

### Privacy and Rate Limits

- The skill never includes file diffs or implementation details in the filed ticket. Only the original reviewer comment text and the link back to the PR.
- Linear and Jira have low rate limits for issue creation. The skill spaces auto-file calls by 500ms when filing more than 3 items.
- For GitHub Issues, the skill checks `gh api rate_limit` before bulk-filing and aborts if remaining quota is below 50.

## Service Level Expectations

The skill embeds the cycle-time discipline from Google eng-practices and Pragmatic Engineer.

| Action | Target |
|--------|--------|
| Acknowledge a new review comment | Within 4 hours of becoming aware |
| First substantive response to a batch | Within 1 business day |
| Batch responses, single push | One push covers all approved replies and fixes for the round |
| Re-request review after addressing | Explicit re-request, accompanied by a `PTAL` comment |
| Synchronous escalation | After two round trips with no convergence |
| Stale PR handling | If no movement for 7 days, the author either pushes a status update or closes the PR |

The skill enforces these by surfacing reminders, never by acting unilaterally. When a thread has been open for more than 4 hours without acknowledgment, the skill prints a notice. When a PR has been idle for more than 7 days, the skill suggests a status update or closure.

## AI Bot Triage Tactics

Full pattern catalog with per-tool false positives lives in `bot-triage.md`. The summary below is the operational ruleset when `--include-bots` is set.

### Severity baseline

Treat every AI-bot comment as P3 until corroborated by a human reviewer or by a verification check. Independent audits show CodeRabbit precision around 50%, Greptile with the highest catch rate but also the highest false-positive rate, Copilot reporting 71% actionable.

### Known false-positive patterns

| Pattern | Common origin |
|---------|---------------|
| Style suggestion that contradicts the project's lint config | CodeRabbit, Sourcery |
| Imagined APIs, like suggesting a `lodash` helper in a project that bans lodash | CodeRabbit |
| "Add a try/catch" on code that intentionally propagates the error | Multiple bots |
| Security warning on input already validated upstream | CodeRabbit, Greptile |
| "Add JSDoc" in a project whose convention is types-as-docs | CodeRabbit |
| Refactor suggestion that does not compile under TypeScript strict | All bots |
| "Consider using async/await" on code that already uses it | Copilot |

### Teach-once playbook

When the bot is wrong, reply with a one-line educational dismissal that names the project rule the bot missed. Example: "Not applicable: project ban on `lodash`. See `CONTRIBUTING.md`." Resolve the thread. CodeRabbit and similar tools learn from dismissals over 2 to 4 weeks.

### Commands cheat sheet

| Command | Effect |
|---------|--------|
| `@coderabbitai pause` in PR body | Pauses re-review during heavy iteration |
| `@coderabbitai resume` | Resumes |
| `@coderabbitai review` | Single re-pass |
| `@coderabbitai ignore` | Disables on this PR |
| `bugbot run` | Triggers a new Cursor BugBot pass |
| `cursor review` | Same |

### Never credit a bot as commit author

The personal CLAUDE.md rule and the broader research both prohibit attributing commits or PRs to AI tooling. The `ai-attribution-blocker.py` hook is the runtime enforcement layer. The skill's draft commit message must not name any AI tool in any author or co-author trailer.

## Multi-Reviewer Conflict Resolution

When two reviewers contradict, the skill surfaces a `conflict` decision instead of executing.

| Pattern | Skill action |
|---------|--------------|
| Reviewer A wants X, Reviewer B wants Y, on the same line | Mark both threads `conflict`. Draft a reply that quotes both verbatim, states the author's slight preference with reasoning, and asks A and B to align before the author pushes |
| Reviewer A approved, Reviewer B has not responded in over 24 hours | Print a notice. Default: do not auto-merge. Suggest a one-time `PTAL` ping to B |
| Reviewer A blocks, Reviewer B has not yet weighed in | Hold the merge. The skill never dismisses a CHANGES_REQUESTED review without an explicit user decision |
| Both reviewers stale for over 2 round trips with no convergence | Tag the threads `synchronous-recommended` and suggest escalation to a tech lead or module owner |

The skill never silently merges or dismisses a CHANGES_REQUESTED review. Re-requesting review is a manual action behind `--re-request <user>`.

## Resolution Convention

Two community conventions exist.

### Default convention from Tidyverse and GitLab

The author resolves only the threads they have fully addressed and that are unambiguous. Anything with an open reply, an open question, a suggestion the author chose not to take, or a request for verification stays open for the reviewer to resolve. This is the default in the skill.

### Alternative convention from Dan Clarke

The person who started the thread resolves. The author never resolves. Opt in with `--resolve-by reviewer`.

In both conventions, the skill never bulk-resolves. Each resolve is a single GraphQL call tied to a specific thread whose action just completed. The `bulk-resolve-blocker.py` hook enforces this at the runtime layer.

### Outdated vs Resolved

GitHub auto-marks comments as `outdated` when the cited line changes. Outdated is not the same as resolved. The skill never relies on `isOutdated == true` as a substitute for an explicit resolution. Force-pushing to mark threads outdated is an anti-pattern flagged in the "As Reviewee" section of `../../standards/code-review.md`.

## Commit Credit Conventions

Use Git trailers to credit human reviewers.

| Trailer | When to use |
|---------|-------------|
| `Co-authored-by: <Name> <email>` | The reviewer wrote a portion of the fix, supplied a non-trivial algorithm, or proposed a change the author took verbatim |
| `Suggested-by: <Name> <email>` | The reviewer suggested the direction. The author implemented it independently |
| `Reviewed-by: <Name> <email>` | The reviewer reviewed and approved the change. Common in kernel and Rust projects |

Apply only to human reviewers. Never to AI tools or any non-human contributor. The `ai-attribution-blocker.py` hook is the runtime enforcement layer.

The skill prompts before adding any credit trailer. The default is no trailer unless the reviewer's input was substantive.

## Rules

- Every drafted reply passes the no-internal-config-leakage check before posting. No `~/.claude/` paths, no rule citations, no checklist numbers in any external output.
- Every code change goes through the full local quality gate before push.
- Resolution requires either a reply or an implemented fix. Silent resolve is forbidden.
- Bulk resolve is forbidden. Each thread is resolved individually after its action completes. The `bulk-resolve-blocker.py` hook backs this rule at runtime.
- `--auto` is the only path that skips per-batch approval. It additionally requires `RESPOND_AUTO_ACK=1` to take effect. Two locks reduce accidental triggers.
- Deferred items must include a ticket URL. If no tracker integration is available, the skill prints a reminder and requires the user to confirm they will file it externally.
- AI bot threads are out of scope by default. `--include-bots` is opt-in for the case where the user wants one flow.
- Account safety: every `gh` call uses `GH_TOKEN=$(gh auth token --user <account>)` inline.
- Never `git push --no-verify`. Never bypass hooks without an explicit user-confirmed env var.
- Force-push is blocked during open CHANGES_REQUESTED reviews unless `--force-during-review` is passed.
- The skill never dismisses, deletes, or downgrades a review that the running user did not author.
- Restore the working tree on any failure inside Phase 6. The skill leaves a clean tree if it cannot complete the batch.

## Platform Reference Files

| File | When to read |
|------|-------------|
| `platform-gitlab.md` | When the detected platform is GitLab. Documents glab CLI and REST API patterns, discussion model, resolve semantics, and bot allowlist |
| `platform-bitbucket.md` | When the detected platform is Bitbucket Cloud. Documents REST API patterns, auth model, and the absence of a native resolve concept |

## Related skills

| Skill | When to use it |
|-------|----------------|
| `/review` | Performing a review on someone else's PR. Generates verdicts using the same Conventional Comments taxonomy |
| `/ship --pipeline` | Unattended handling of AI bot threads and CI monitoring without human-thread work. When `RESPOND_DRIVES_PIPELINE=1` is set, `/ship --pipeline` delegates the AI-bot sweep to this skill via `--auto --include-bots`, unifying the vocabulary across both flows |
| `/ship pr` | Creating or updating a PR before review starts |
| `/test` | Running tests after a code change before posting "Fixed in `<SHA>`" |
| `/investigate` | When a reviewer reports a bug that does not reproduce, before drafting the reply |
| `/plan` | When a reviewer requests an architectural change too large for inline reply |

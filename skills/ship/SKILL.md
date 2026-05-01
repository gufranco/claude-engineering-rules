---
name: ship
description: Ship code through the full delivery pipeline. Subcommands: commit, pr, release, checks, worktree. Handles semantic commits, pull requests with CI monitoring, tagged releases, pipeline diagnosis, and parallel worktree management. Use when user says "commit", "create a PR", "push", "release", "check CI", "pipeline status", "worktree", or wants to move code from working directory to production. Do NOT use for code review (use /review), running tests (use /test), or planning (use /plan).
sensitive: true
---
Unified delivery skill for getting code from working directory to production. Replaces standalone `/commit`, `/pr`, `/release`, `/checks`, and `/worktree` skills.

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/ship` or `/ship commit` | Create semantic commits (default) |
| `/ship pr` | Create or update a pull request |
| `/ship release` | Create a tagged release with changelog |
| `/ship checks` | Monitor CI/CD pipeline and diagnose failures |
| `/ship worktree` | Manage git worktrees for parallel development |

If no subcommand is given, default to `commit`.

---

## commit

Analyze all uncommitted changes and create semantic commits following the conventional commit format.

### When to use

- After completing a task and ready to save progress.
- When multiple unrelated changes need separate commits.
- Before creating a PR, to ensure clean commit history.

### Arguments

- No arguments: commit and ask whether to push.
- `--push`: commit and push automatically.
- `--pipeline`: commit, push, ensure a PR exists (open one if missing), and stay in a monitoring loop until **CI is 100% green AND there are zero open AI-tool review threads**. Implies push. If no PR exists on the current branch, runs the `pr` flow (with `--no-pipeline` to avoid recursion) before entering Pipeline Monitoring. On CI failure, diagnoses, fixes, and re-pushes. On open AI-tool comments (CodeRabbit, Copilot, Greptile, Sourcery, etc.), addresses every actionable finding, pushes the fix, and resolves the thread. The loop only exits when both conditions hold simultaneously on the latest SHA.

### Steps

1. Run **in parallel**: `git status`, `git diff`, `git diff --cached`, `git log --oneline -10`.
2. Group related changes into logical units. Each group becomes one commit:
   - Same feature/module together.
   - Unrelated changes in separate commits.
   - Tests go with the code they test.
3. For each group: stage specific files (`git add <file>`, never `-A` or `.`), commit with format below.
4. Run **in parallel**: `git status`, `git log --oneline` to verify.
5. Push logic:
   - `--push`: push immediately.
   - `--pipeline` without `--push`: ask "Push to remote and monitor pipeline?"
   - No flags: ask "Want me to push to remote?"
   - Check upstream: `git rev-parse --abbrev-ref @{upstream}`. Use `-u origin <branch>` if none.
6. If `--pipeline`:
   - Check if a PR exists for the current branch (`gh pr view` / `glab mr view`).
   - If none exists, invoke the `pr` flow with `--no-pipeline` to create the PR (skipping its own monitoring loop), then continue.
   - Enter the Pipeline Monitoring loop (see below).

### Commit Message Format

Follow `rules/git-workflow.md`. Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Subject: imperative mood, no caps, no period, max 50 chars. Body: wrap at 72, explain WHAT and WHY. Footer: `BREAKING CHANGE:`, `Fixes #`, `Closes #`, `Refs #`.

---

## pr

Create or update a pull request with a structured description. Supports GitHub and GitLab.

### When to use

- After committing to a feature branch and ready for review.
- When updating an existing PR description.
- When creating a draft PR for early feedback.

### Arguments

- No arguments: create a new PR.
- `--draft`: create as draft.
- `--base <branch>`: target specific base branch.
- `--reviewer <user>`: request review (repeatable).
- `--assignee <user>`: assign PR (defaults to `@me`).
- `--label <name>`: add label (repeatable).
- `--no-pipeline`: skip CI monitoring after creation.
- `--docs`: automatically update stale documentation without asking.
- `update` or a PR number: update existing PR.

### Steps

1. **Gather context** (parallel): `git status --porcelain`, `git remote get-url origin`, `git branch --show-current`. Stop if uncommitted changes or on main. Detect CLI tool (`gh`/`glab`). **Resolve account** per `standards/borrow-restore.md`.
2. **Check existing PR and base branch** (parallel): look up existing PR, detect base branch (unless `--base`). If PR exists and no `update` flag, show URL and ask.
3. `git fetch origin`, `git log --oneline origin/<base>..HEAD`. Stop if no commits.
4. **Run quality gate**: detect and run test, lint, build. Stop if they fail.
5. **Rebase**: `git rebase origin/<base>`. If conflicts, `git rebase --abort` and stop. Track if rebase rewrote history for force-push.
6. **Check PR size** (parallel): `git diff origin/<base>...HEAD --stat` and full diff. Warn at 400+ lines, confirm at 1000+.
7. **Self-review**: scan for debug statements, TODO/FIXME, accidentally committed files, binaries.
8. **Extract context**: check branch/commits for ticket patterns, check if frontend files changed (suggest screenshots).
9. **Push**: use `-u` if no upstream, `--force-with-lease` only if rebase rewrote history.
10. **Build title and description**: detect PR template (`.github/PULL_REQUEST_TEMPLATE.md` or GitLab equivalent). Use What/How/Testing structure. Scale to PR size.
11. **Create/update**: write body to temp file. `gh pr create --body-file` or `glab mr create --description-file`. Self-assign by default. Clean up temp file.
12. Show PR URL.
13. **Documentation staleness check.** Read project documentation files (README.md, CONTRIBUTING.md, docs/ directory) and cross-reference against the diff:
    - New features without corresponding documentation.
    - Removed features still documented.
    - Changed APIs with stale examples.
    - New environment variables not in `.env.example`.
    - New CLI commands or scripts not documented.
    If stale documentation is found, list the gaps and offer to update. If `--docs` flag is passed, update automatically without asking.
14. **Restore account** per `standards/borrow-restore.md`.
15. Enter Pipeline Monitoring loop unless `--no-pipeline`. The loop monitors both CI checks AND AI-tool review threads, and only exits when both are clean.

### PR Title

Conventional commit style when it fits. Max 70 chars. Prefix ticket ID if available.

### PR Description

- **Small PR**: one paragraph, no headers.
- **Standard PR**: What, How, Testing sections. Add Breaking Changes only if applicable.
- Concise, direct. No filler.

---

## release

Create a tagged release with an auto-generated changelog from conventional commits.

### When to use

- After merging all planned changes to main and ready to release.
- With `--dry-run` to preview before creating.

### Arguments

- No arguments: auto-detect next version from commit types.
- A version (e.g. `1.2.0`): use that exact version.
- `--dry-run`: show what would be released without creating anything.

### Steps

1. **Gather context** (parallel): `git remote get-url origin`, `git describe --tags --abbrev=0`, `git status --porcelain`. Detect CLI tool. **Resolve account**. Stop if dirty.
2. `git log --oneline <last-tag>..HEAD`. Stop if no commits.
3. Determine version: parse last tag as semver. `BREAKING CHANGE`/`!` = major, `feat` = minor, `fix`/`perf`/`refactor` = patch. Only `chore`/`docs`/`style`/`test`/`build`/`ci` = no bump.
4. Generate changelog grouped by type: Features, Bug fixes, Performance, Other changes, Breaking changes.
5. If `--dry-run`, show and stop.
6. **Run quality gate**: test, lint, build. Stop if they fail.
7. Present version and changelog for approval.
8. After approval: `git tag -a v<version> -m "v<version>"`, `git push origin v<version>`, `gh release create` or `glab release create` with notes-file. Clean up temp file.
9. Show release URL.
10. **Restore account**.

---

## checks

Monitor CI/CD pipeline checks and diagnose failures. Diagnosis only, no auto-fix.

### When to use

- After pushing or creating a PR.
- When a pipeline fails and you need diagnosis.

### Arguments

- No arguments: check current branch.
- A PR number: check that specific PR.

### Steps

1. **Gather context** (parallel): `git remote get-url origin`, `git branch --show-current`. Detect CLI tool. **Resolve account**.
2. Check for PR (or use provided number). Fall back to branch pipelines.
3. Check status: `gh pr checks` or `glab ci status`.
4. If passing, report and stop.
5. If running, wait with timeout: `timeout 600 gh pr checks --watch` or equivalent. Report if timeout reached.
6. If failed: fetch logs (parallel) with `gh run view <id> --log-failed` or `glab ci trace <job-id>`. Search for existing fixes first.
7. Present diagnosis per failure: check name, URL, error, log excerpt.
8. Suggest next steps but do not auto-fix.
9. **Restore account**.

---

## worktree

Manage git worktrees for parallel development.

### Subcommands

| Invocation | Action |
|-----------|--------|
| `/ship worktree init <task1> \| <task2>` | Create worktrees from pipe-separated tasks |
| `/ship worktree deliver` | Commit, push, and create PR from worktree |
| `/ship worktree check` | Show status of all worktrees |
| `/ship worktree cleanup` | Remove worktrees for merged branches |

### init

1. Verify: git repo, not inside worktree, get repo root and branch.
2. Parse tasks on `|`. Each segment becomes a worktree.
3. For each: branch `wt/<kebab-case>`, path `<root>/.worktrees/<name>`, `git worktree add -b <branch> <path>`. Write `.worktree-task.md`. Ask about package install.
4. Present table: path, branch, task.

### deliver

1. Verify inside a worktree.
2. Gather state (parallel): status, commits, task file, remote, branch. **Resolve account**.
3. Stage and commit (worktrees are task-scoped). Remove `.worktree-task.md` from staging.
4. Push with `-u`.
5. Create PR using task description. Follow PR conventions.
6. **Restore account**. Show PR URL.

### check

1. `git worktree list --porcelain`.
2. For each (parallel): branch, commit count, uncommitted changes, task file.
3. Present as table.

### cleanup

- Default: remove worktrees whose branch is merged.
- `--all`: all `wt/*` worktrees (warn about unmerged work).
- `--branch <name>`: specific worktree.
- `--dry-run`: show what would be removed.
- Remove worktree, delete local branch, optionally delete remote branch (ask first). Run `git worktree prune`.

---

## Pipeline Monitoring (shared by commit and pr)

The monitoring loop has **two parallel exit conditions that must BOTH hold on the latest pushed SHA**:

1. Every functional CI check is green (manual gates like `lead-approval` are excluded).
2. Every actionable AI-tool review thread is resolved (CodeRabbit, GitHub Copilot, Greptile, Sourcery, Korbit, Bito, Codium, Qodo, etc.).

Do not declare the loop complete while either condition is open. If a fix is pushed for one condition, both conditions must be re-verified on the new SHA before exiting.

### Step 1: Detect platform and locate checks

Run **in parallel**: `git remote get-url origin`, `git branch --show-current`. Detect CLI tool. **Resolve account**. Check if PR exists.

If no PR exists and the caller invoked `--pipeline`, fall through to the `pr` flow with `--no-pipeline` (steps 1-14) to open one, then re-evaluate. Many CI configs only fire on `pull_request` events; without a PR there is nothing to monitor.

### Step 2: Wait for CI checks

- With PR: `timeout 600 gh pr checks --watch` or `glab ci status --wait`.
- Without PR (only when CI fires on push, e.g. branch protections or scheduled workflows): `gh run watch <id>` or `glab ci status --wait`.
- Exit code 124 = timeout; report and stop. Schedule a wakeup and re-poll if the loop is still active.

### Step 3: Evaluate CI

- All functional checks pass: proceed to Step 6 (AI comment sweep). Do NOT exit yet.
- Any functional check fails: proceed to Step 4.

### Step 4: Diagnose CI failure

Fetch failed logs (parallel). Search for existing fixes first. Present diagnosis per failure.

### Step 5: Fix CI failure

- Apply fix, stage specific files, commit (its own commit, conventional format), push.
- Return to Step 2 on the new SHA.
- Stop only on user request or after the guardrail cycle limit.

### Step 6: AI-tool comment sweep

Fetch every open review thread authored by AI bots and resolve them all. This step is mandatory in `--pipeline` mode and runs every time CI is green, including after a CI fix push.

#### 6a: Fetch open AI-tool threads

Use the platform's GraphQL API to enumerate review threads with `isResolved: false` whose first comment author matches a known AI bot. The match is case-insensitive on the login and includes (non-exhaustive): `coderabbit`, `copilot`, `greptile`, `sourcery`, `korbit`, `bito`, `qodo`, `codium`, `cursor`, `tabnine`, `gemini-code-assist`, `claude`.

GitHub example:

```bash
gh api graphql -f query='query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes { databaseId author { login } path body }
          }
        }
      }
    }
  }
}' -F owner=<owner> -F repo=<repo> -F pr=<number>
```

Filter the result to threads where `isResolved == false` and the first comment's author login matches the AI-bot list.

#### 6b: Triage each finding

For every open thread, read the full comment body (use `gh api repos/<owner>/<repo>/pulls/comments/<databaseId> --jq '.body'` for the unabridged text) and classify:

| Classification | Action |
|---------------|--------|
| Actionable + valid | Apply the fix. Each fix becomes its own commit. |
| Already resolved by prior code | Verify the current code resolves the issue, then close the thread. |
| False positive | Reply with a one-sentence explanation, then close the thread. |
| Out of scope | Reply explaining why, link a follow-up ticket if relevant, then close the thread. |

Never close a thread without either fixing the issue or posting a reply that justifies dismissal.

#### 6c: Apply fixes

Group related fixes per file when possible. Run formatter, linter, typechecker, tests, and build locally before committing. Push once per logical fix group.

#### 6d: Resolve threads

After the fix is verified and pushed (or after a justified dismissal reply), resolve the thread. GitHub:

```bash
gh api graphql -f query='mutation($threadId: ID!) {
  resolveReviewThread(input: { threadId: $threadId }) {
    thread { id isResolved }
  }
}' -F threadId=<thread-node-id>
```

GitLab uses `glab api` with the equivalent `mark_thread_as_resolved` mutation, or `glab mr resolve-thread`.

#### 6e: Loop back

After every push triggered by Step 6, return to Step 2. New AI tools often re-review the new SHA and may post fresh threads. The loop is not complete until a full pass finds zero open AI threads AND CI is green on the same SHA.

### Step 7: Final verification and exit

Only when **both** conditions hold on the latest SHA:

- `gh pr checks <pr>` shows every functional check as `pass` (manual gates excluded).
- `gh api graphql` review-thread query returns zero AI-bot threads with `isResolved == false`.

Report a one-line summary: PR URL, latest SHA, count of CI checks passed, count of AI threads resolved.

### Guardrails

- Max 5 fix-and-retry cycles per loop run. Above the limit, stop and ask the user how to proceed.
- Only fix what you can confidently fix. Dismiss with a reply when in doubt; never silently close.
- Each fix is its own commit with a conventional-commit message.
- Never skip hooks (`--no-verify`).
- Never resolve a thread without verifying the fix is on the pushed SHA.
- Never resolve threads authored by humans automatically — Step 6 covers AI bots only.
- Use `ScheduleWakeup` (or equivalent) when waiting on CI or AI re-review to avoid burning context on tight polling loops.
- **Restore account** on exit.

---

## Rules

- Never combine unrelated changes in one commit.
- Never use `git add -A` or `git add .`.
- Never include files with secrets.
- Always detect git platform from remote URL. Never assume GitHub or GitLab.
- Always detect base branch dynamically.
- Always check for uncommitted changes before PR operations.
- Always write body to temp file for shell safety.
- Only force push with `--force-with-lease`, only after rebase.
- Never merge PRs. Only create or update.
- Never auto-approve Terraform applies or releases without user approval.
- Always restore account per `standards/borrow-restore.md`.
- `--pipeline` and any `pr` flow that opens a PR must run the full Pipeline Monitoring loop. The loop only exits when CI is 100% green AND every AI-tool review thread is resolved on the latest pushed SHA. Resolving partial state (CI green but threads open, or threads resolved but CI red) is not "done".

## Related skills

- `/review` -- Review code before or after creating a PR.
- `/test` -- Run tests before shipping.
- `/infra` -- Manage Docker/DB before shipping.
- `/deploy` -- Merge and deploy after the PR is approved.

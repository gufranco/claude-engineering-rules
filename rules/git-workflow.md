# Git Workflow

## Commit Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

**Subject Rules:**

- Imperative mood: "add" not "added" or "adds"
- No caps at start, no period at end
- Max 50 characters

**Body:** Wrap at 72 characters. Explain WHAT and WHY, not HOW.

**Footer:**

- `BREAKING CHANGE:` for breaking changes, or `!` after type/scope
- `Fixes #123`, `Closes #456`, `Refs #789`
- **NEVER** add `Co-authored-by` lines referencing any AI

## Decision Trailers (Optional)

Commit messages may include trailers that record decision context. These are optional but must follow the correct format when present. The `conventional-commits.sh` hook validates format.

```
refactor(auth): replace session store with JWT

Switched from server-side sessions to short-lived JWTs with refresh
token rotation. Session store was a single point of failure.

Rejected: Redis session store | added infrastructure dependency for a stateless service
Constraint: tokens must be revocable within 15 minutes per compliance policy
Risk: refresh token rotation adds complexity to the mobile client
```

| Trailer | Format | Purpose |
|---------|--------|---------|
| `Rejected` | `Rejected: <alternative> \| <reason>` | Documents an approach that was considered and discarded. The pipe separates what from why. Prevents future engineers from re-exploring dead ends |
| `Constraint` | `Constraint: <description>` | Records a constraint that shaped the decision. External requirements, compliance rules, performance budgets |
| `Risk` | `Risk: <description>` | Flags a known risk introduced by the change. Future engineers know what to watch for |

Rules:

- Trailers go in the footer section, after the body
- Each trailer is one line
- `Rejected` must include the pipe separator between alternative and reason
- Multiple trailers of the same type are allowed
- Do not add trailers to trivial commits (typos, formatting, config tweaks)

## Branch Naming

```
<type>/<ticket-id>-<description>
```

Types: `feature/`, `bugfix/`, `hotfix/`, `release/`, `chore/`

## Local Quality Gate (MANDATORY)

Before every `git commit` or `git push`, run all available quality tools in the project. The goal is to catch problems locally instead of waiting for CI pipeline feedback.

**Required checks, in order:**

1. **Format**: run the project's formatter. Code that fails formatting is not ready to commit.
2. **Lint**: run the project's linter. Zero warnings, zero errors.
3. **Type check**: if the project has a type checker, run it. Zero errors.
4. **Test**: run the full test suite. All tests pass.
5. **Build**: run the build command. Clean build, zero warnings, zero errors.

Detect the correct commands from the project's package manager, lockfile, and scripts. Common patterns:

| Tool area | Detection |
|-----------|-----------|
| Formatter | `prettier`, `black`, `gofmt`, `rustfmt` in scripts or devDependencies |
| Linter | `eslint`, `ruff`, `golangci-lint`, `clippy` in scripts or devDependencies |
| Type check | `tsc --noEmit`, `mypy`, `pyright` in scripts or devDependencies |
| Test | `test` or `test:unit` script, `pytest`, `go test`, `cargo test` |
| Build | `build` script, `go build`, `cargo build` |

**Rules:**

- If a check fails, fix the issue before committing. Do not skip checks.
- If the project lacks a specific tool, skip that step. Do not invent checks that do not exist.
- Show the output of each check. Silent success is not evidence.
- This gate applies to every commit, not just the final one before a push.
- Stale results do not count. If code changed since the last run, run again.
- **Formatter and linter are not always the same tool.** Many projects have a `lint` script that runs ESLint (or equivalent) without invoking Prettier. Running `pnpm lint` in that case does not satisfy step 1. Always check whether the lint script includes the formatter. If it does not, run `prettier --check` (or the equivalent check-mode command) as a separate explicit step. A Prettier failure caught only by CI forces an extra commit and an extra pipeline run.
- **When a format check fails for `package.json` and the project uses `prettier-plugin-packagejson`**, do not guess the field order manually. The plugin applies its own schema-based ordering that is not alphabetical. Run `prettier --write package.json` locally with the project's exact plugin version installed and read the result. One local run gives the correct format. Repeated manual attempts without running the formatter do not.

## Schema and Environment Sync (MANDATORY)

When a commit changes the database schema or environment variable configuration, these additional steps are required before committing.

**Database schema changes (Prisma, migrations):**

1. Push to the dev database: `npx prisma db push`
2. Push to the test database using the connection string from `.env.test`, not a manually constructed URL
3. Regenerate the Prisma client: `npx prisma generate`
4. Run the full test suite to verify no regressions
5. Add new models to the test cleanup order in `test/setup.ts`

**Environment variable changes (add, remove, rename, change default):**

1. Update `.env.example` with the new variable and a placeholder value
2. Update `.env.test` to provide a test-appropriate value
3. Update `.env.local` if it exists
4. Grep all CI workflow files for references to the changed variable
5. Grep all Docker Compose files for references
6. Run the full test suite. Env schema mismatches cause mass test failures that look like code bugs

**Running containers are not updated by file changes.** If you change `docker-compose.yml` or `docker-compose.test.yml`, the running containers still use the old configuration. Either restart the containers or keep the change backward-compatible with running instances.

## CI/CD Monitoring (MANDATORY)

After ANY push:

1. **Cancel superseded runs.** List all in-progress and queued runs on the branch. Cancel every run except the one triggered by the latest push. Older runs test stale code and waste runner minutes.
2. Run `gh pr checks --watch` or `gh run watch <latest-id>`
3. Wait for ALL checks
4. Review CI annotations and warnings. Deprecation notices, version warnings, and non-fatal alerts require a fix in the same task
5. If failed: `gh run view <id> --log-failed`
6. Before fixing: search for an existing fix in source branch, open PRs, and remote branches
7. If no existing fix: Fix, push, repeat until green

**Never** mark task complete with failing/running pipeline or unresolved warnings.

**Batch fixes before pushing.** When CI fails with multiple issues, fix all of them locally before pushing again. One push with all fixes, not one push per fix. Each push triggers a full pipeline run across all platforms.

**Rate limit awareness.** `gh run watch` polls every 3 seconds (~1200 requests/hour). Never run multiple watchers concurrently. Before starting a watcher, check quota with `gh api rate_limit`. If remaining quota is below 500, use one-shot `gh run view <id>` checks instead of continuous polling.

## CI File Validation

Before committing changes to CI workflow files, run the relevant linters locally to avoid fix-push-fail cycles:

| File type | Tool | Command |
|-----------|------|---------|
| `.github/workflows/*.yml` | actionlint | `actionlint` |
| Any `.yml` / `.yaml` | yamllint | `yamllint -d "{extends: default, rules: {line-length: disable}}" <file>` |
| Shell scripts referenced by CI | shellcheck | `shellcheck <file>` |

If a tool is not installed locally, install it before proceeding. Do not skip the check and hope CI catches it.

## PR/MR Creation

**Title:** Clear, specific summary of what the PR accomplishes. Describe the outcome, not the process.
- Good: `feat(auth): add SSO login with Google and GitHub providers`
- Bad: `update auth`, `fix stuff`, `changes`

When a ticket ID exists, prefix it: `<TICKET-ID>: <description>`

**Description structure:**

- **What**: One paragraph explaining what changed and why. A reviewer reading only this paragraph should understand the full picture.
- **How**: Key implementation decisions, trade-offs, and anything non-obvious. Skip trivial details the diff already shows.
- **Testing**: How the changes were verified. Include commands, screenshots, or steps to reproduce.
- **Breaking changes**: If any, list them with migration steps.

Before opening:

1. Identify the base branch from git, never hardcode it
2. Fetch and rebase: `git fetch origin && git rebase origin/<base>`
3. Resolve conflicts if any, run tests locally

Prefer CLI over web UI:

```bash
gh pr create --title "<desc>" --body-file pr.md
gh pr create --draft --title "<TICKET-ID>: WIP"
gh pr merge <number> --squash --delete-branch
```

**Dual-base PRs (same change targeting two branches):** never use `--delete-branch` on the first merge. GitHub auto-closes any other open PR whose head is the deleted branch. Use separate branches (`fix/foo-develop`, `fix/foo-main`) from the start, or omit `--delete-branch` until both PRs are merged.

## Shallow Clone Detection

Before running `git rebase` on a repo that may be a shallow clone (repos in `/tmp/`, CI workspaces, repos cloned with `--depth`):

1. Check: `git rev-parse --is-shallow-repository`
2. If `true`: run `git fetch --unshallow` before rebasing.

Symptom when missed: `error: update-ref requires a fully qualified refname e.g. refs/heads/grafted`.

## CI Not Triggering After Push

Before diagnosing a CI pipeline failure, check branch mergeability:

```bash
GH_TOKEN=... gh pr view <number> --repo <owner/repo> --json mergeable,mergeableState
```

If `mergeableState` is `dirty`, the branch has merge conflicts. GitHub Actions `pull_request.synchronize` will not start new runs on a conflicted branch. Resolve conflicts and push first, then diagnose CI.

## Conflict Resolution

```bash
git fetch origin && git rebase origin/<base>
# Resolve conflicts manually
git add <file> && git rebase --continue
# Test locally, then:
git push --force-with-lease
```

## Push Strategy

Every `git push` triggers a CI pipeline run. Pipeline runs consume paid runner minutes. Minimize pushes.

**Rules:**

- Commit locally as often as needed. Small, atomic commits are good.
- Do NOT push after every commit. Accumulate local commits until the task is complete and all local quality gates pass.
- Push once at the end of the task, after format + lint + typecheck + test + build all pass locally.
- If the task spans multiple sessions, push at the end of the last session, not at the end of each session.
- When a task requires a PR, push once to create the PR. Do not push work-in-progress.
- After push, monitor CI as described in "CI/CD Monitoring."

**Exceptions where intermediate pushes are acceptable:**

- The user explicitly asks to push.
- A PR review is needed before continuing (push to get feedback).
- The branch needs to be shared with another developer.

**Batch CI fixes.** When CI fails with multiple issues, fix all of them locally before pushing. One push with all fixes, not one push per fix.

**Agent push prohibition.** Subagents must never push to remote. Only the main orchestrator pushes, once, at the end of all work. Agent prompts must explicitly state: "Do not push." If an agent needs to verify CI, the orchestrator handles the push and monitoring after all agent work is collected and verified locally.

## Rollback Strategy

If a change causes problems:

1. `git revert <commit>`, then push
2. Analyze what went wrong
3. Fix properly in new commit

**Never** force push or amend pushed commits.

## Migration Ordering

When a project uses sequential migrations (Prisma, Flyway, Knex, etc.), migrations for the current task must always have the latest timestamps. Other team members may merge migrations while you work.

Before every commit, push, rebase, or PR:

1. List existing migrations: `ls <migrations_dir> | sort | tail -5`
2. If your migrations are not last, rename them with newer timestamps
3. Verify ordering again after rebase (rebasing can interleave with newly merged migrations)

## Migration Idempotency

Every migration must be safe to run more than once. Assume the migration might be applied to a database where the objects already exist.

- Use `IF NOT EXISTS` for `CREATE TABLE`, `CREATE INDEX`, `CREATE EXTENSION`
- Use `DO $$ IF NOT EXISTS ... END $$` for statements that lack native `IF NOT EXISTS` support (e.g., `CREATE MATERIALIZED VIEW` in PostgreSQL)
- Use `IF EXISTS` for `DROP` statements
- Never assume a clean slate. Another migration, manual intervention, or partial deploy might have created the object already

## CHANGELOG Writing

When a project has a CHANGELOG.md:

- Write for users, not contributors. Lead with what the user can now DO
- Internal refactors and contributor-facing changes go in a separate "Internal" section
- Each entry should make someone think "I want to try that"
- Use past tense for completed work: "Added", "Fixed", "Removed"
- Group by: Added, Changed, Fixed, Removed, Security
- Never list commit hashes or PR numbers as the primary content

## Ignored Artifacts

Build output directories must never be committed:

- `dist/`, `build/`, `.next/`, `out/`, `coverage/`, `node_modules/`
- Verify these are in `.gitignore` when setting up or reviewing a project

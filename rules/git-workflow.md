# Git Workflow

## Commit Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

**Subject:** imperative mood, no caps at start, no period at end, max 50 characters.

**Body:** wrap at 72 characters. Explain WHAT and WHY, not HOW.

**Footer:** `BREAKING CHANGE:` or `!` after type/scope. `Fixes #123`, `Closes #456`, `Refs #789`. **NEVER** add `Co-authored-by` lines referencing any AI.

## Decision Trailers (Optional)

Optional trailers in the footer record decision context. The `conventional-commits.sh` hook validates format.

| Trailer | Format | Purpose |
|---------|--------|---------|
| `Rejected` | `Rejected: <alternative> \| <reason>` | Documents a discarded approach. Prevents re-exploring dead ends |
| `Constraint` | `Constraint: <description>` | Records a constraint that shaped the decision |
| `Risk` | `Risk: <description>` | Flags a known risk introduced by the change |

- Trailers go in the footer, after the body. One trailer per line
- `Rejected` must include the pipe separator between alternative and reason
- Do not add trailers to trivial commits (typos, formatting, config tweaks)

## Branch Naming

```
<type>/<ticket-id>-<description>
```

Types: `feature/`, `bugfix/`, `hotfix/`, `release/`, `chore/`

## Local Quality Gate (MANDATORY)

Before every `git commit` or `git push`, run all available quality tools. Required checks in order:

1. **Format**: run the project's formatter. Failing formatting is not ready to commit
2. **Lint**: zero warnings, zero errors
3. **Type check**: zero errors
4. **Test**: full suite, all pass
5. **Build**: clean build, zero warnings, zero errors

Rules:
- Fix failures before committing. Do not skip checks
- Show the output of each check. Silent success is not evidence
- This gate applies to every commit, not just the final one before a push
- Stale results do not count. If code changed since the last run, run again
- **Formatter and linter are not always the same tool.** If the `lint` script does not invoke Prettier, run `prettier --check` as a separate explicit step
- **When a format check fails for `package.json` with `prettier-plugin-packagejson`**: run `prettier --write package.json` locally. The plugin applies schema-based ordering that is not alphabetical. Do not guess the field order manually

## Schema and Environment Sync (MANDATORY)

**Database schema changes (Prisma, migrations):**
1. `npx prisma db push` to dev database
2. Push to test database using connection string from `.env.test`
3. `npx prisma generate`
4. Run the full test suite
5. Add new models to test cleanup order in `test/setup.ts`

**Environment variable changes (add, remove, rename, change default):**
1. Update `.env.example` with placeholder value
2. Update `.env.test` with test-appropriate value
3. Update `.env.local` if it exists
4. Grep all CI workflow files for references
5. Grep all Docker Compose files for references
6. Run the full test suite

**Running containers are not updated by file changes.** If you change `docker-compose.yml`, restart the containers or keep the change backward-compatible.

## CI/CD Monitoring (MANDATORY)

After ANY push:
1. **Cancel superseded runs.** Cancel every run on the branch except the latest
2. Run `gh pr checks --watch` or `gh run watch <latest-id>`
3. Wait for ALL checks
4. Review CI annotations and warnings. Deprecation notices and non-fatal alerts require a fix in the same task
5. If failed: `gh run view <id> --log-failed`
6. Before fixing: search for an existing fix in open PRs and remote branches
7. Fix, push, repeat until green

**Never** mark task complete with failing/running pipeline or unresolved warnings.

**Batch fixes.** When CI fails with multiple issues, fix all locally before pushing. One push with all fixes, not one per fix.

**Rate limit awareness.** `gh run watch` polls every 3 seconds (~1200/hour). Never run multiple watchers concurrently. Check quota with `gh api rate_limit` before starting. If remaining is below 500, use one-shot `gh run view <id>` instead.

**Agent push prohibition.** Subagents must never push to remote. Only the main orchestrator pushes, once, at the end of all work.

## CI File Validation

Before committing changes to CI workflow files:

| File type | Tool | Command |
|-----------|------|---------|
| `.github/workflows/*.yml` | actionlint | `actionlint` |
| Any `.yml` / `.yaml` | yamllint | `yamllint -d "{extends: default, rules: {line-length: disable}}" <file>` |
| Shell scripts referenced by CI | shellcheck | `shellcheck <file>` |

If a tool is not installed locally, install it before proceeding.

## PR/MR Creation

**Title:** clear, specific, outcome-focused. When a ticket ID exists, prefix it: `<TICKET-ID>: <description>`.

**Description structure:**
- **What**: one paragraph, what changed and why. A reviewer reading only this should understand the full picture
- **How**: key decisions, trade-offs, non-obvious choices. Skip trivial details the diff shows
- **Testing**: how verified. Include commands, screenshots, or reproduction steps
- **Breaking changes**: list with migration steps

Before opening: identify base branch from git (never hardcode), fetch and rebase: `git fetch origin && git rebase origin/<base>`.

```bash
gh pr create --title "<desc>" --body-file pr.md
gh pr create --draft --title "<TICKET-ID>: WIP"
gh pr merge <number> --squash --delete-branch
```

**Dual-base PRs:** never use `--delete-branch` on the first merge. Use separate branches (`fix/foo-develop`, `fix/foo-main`) from the start.

## Shallow Clone Detection

Before running `git rebase` on a repo in `/tmp/`, a CI workspace, or cloned with `--depth`:
1. `git rev-parse --is-shallow-repository`
2. If `true`: run `git fetch --unshallow` before rebasing

Symptom when missed: `error: update-ref requires a fully qualified refname`.

## CI Not Triggering After Push

```bash
GH_TOKEN=... gh pr view <number> --repo <owner/repo> --json mergeable,mergeableState
```

If `mergeableState` is `dirty`, the branch has merge conflicts. Resolve and push before diagnosing CI.

## Conflict Resolution

```bash
git fetch origin && git rebase origin/<base>
git add <file> && git rebase --continue
git push --force-with-lease
```

## Push Strategy

- Commit locally as often as needed. Do NOT push after every commit
- Push once at the end of the task, after format + lint + typecheck + test + build all pass locally
- When a task requires a PR, push once to create the PR. Do not push work-in-progress
- After push, monitor CI as described above

Intermediate pushes are acceptable when: the user explicitly asks, a PR review is needed before continuing, or the branch must be shared.

## Rollback Strategy

1. `git revert <commit>`, then push
2. Analyze what went wrong
3. Fix properly in a new commit

**Never** force push or amend pushed commits.

## Migration Ordering

Migrations for the current task must always have the latest timestamps.

Before every commit, push, rebase, or PR:
1. `ls <migrations_dir> | sort | tail -5`
2. If your migrations are not last, rename them with newer timestamps
3. Verify ordering again after rebase

## Migration Idempotency

Every migration must be safe to run more than once.

- Use `IF NOT EXISTS` for `CREATE TABLE`, `CREATE INDEX`, `CREATE EXTENSION`
- Use `DO $$ IF NOT EXISTS ... END $$` for statements that lack native `IF NOT EXISTS` support
- Use `IF EXISTS` for `DROP` statements
- Never assume a clean slate

## CHANGELOG Writing

- Write for users. Lead with what the user can now DO
- Internal refactors go in a separate "Internal" section
- Use past tense: "Added", "Fixed", "Removed"
- Group by: Added, Changed, Fixed, Removed, Security
- Never list commit hashes or PR numbers as the primary content

## Ignored Artifacts

Never commit: `dist/`, `build/`, `.next/`, `out/`, `coverage/`, `node_modules/`. Verify these are in `.gitignore` when setting up or reviewing a project.

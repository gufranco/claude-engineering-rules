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

## CI/CD Monitoring (MANDATORY)

After ANY push:

1. Run `gh pr checks --watch`
2. Wait for ALL checks
3. Review CI annotations and warnings. Deprecation notices, version warnings, and non-fatal alerts require a fix in the same task
4. If failed: `gh run view <id> --log-failed`
5. Before fixing: search for an existing fix in source branch, open PRs, and remote branches
6. If no existing fix: Fix, push, repeat until green

**Never** mark task complete with failing/running pipeline or unresolved warnings.

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

## Conflict Resolution

```bash
git fetch origin && git rebase origin/<base>
# Resolve conflicts manually
git add <file> && git rebase --continue
# Test locally, then:
git push --force-with-lease
```

## Post-Task Workflow

After completing significant features:

1. Stage and commit with conventional message
2. Push to remote: `git push`
3. Verify remote is updated

**Keep remote in sync.** Do not accumulate local-only commits.

## Rollback Strategy

If a change causes problems:

1. `git revert <commit>`, then push
2. Analyze what went wrong
3. Fix properly in new commit

**Never** force push or amend pushed commits.

## Ignored Artifacts

Build output directories must never be committed:

- `dist/`, `build/`, `.next/`, `out/`, `coverage/`, `node_modules/`
- Verify these are in `.gitignore` when setting up or reviewing a project

---
name: pr-summary
description: Generate PR summary with reviewer suggestions based on file ownership. Fetches PR data, summarizes changes, highlights risks, and recommends reviewers from git history. Use when user says "pr summary", "summarize this PR", "who should review this", "generate PR description", or wants a reviewer-ready summary of a pull request. Do NOT use for code review (use /review), creating PRs (use /ship pr), or checking CI status (use /ship checks).
---

Generates a reviewer-friendly summary of a pull request and suggests reviewers based on file ownership history.

## Arguments

| Invocation | Action |
|-----------|--------|
| `/pr-summary` | Summarize the PR on the current branch |
| `/pr-summary <number>` | Summarize a specific PR by number |

## Process

### 1. Fetch PR Data

Determine the GitHub account from the git remote using `../../rules/github-accounts.md`.

```bash
GH_TOKEN=$(gh auth token --user <account>) gh pr view <number> --json title,body,files,additions,deletions,commits,labels,baseRefName,headRefName,author,reviewRequests
```

If no number is given, detect the current branch and find its PR:
```bash
GH_TOKEN=$(gh auth token --user <account>) gh pr view --json title,body,files,additions,deletions,commits,labels,baseRefName,headRefName,author,reviewRequests
```

### 2. Analyze Changes

1. **Categorize files.** Group changed files by type:

   | Category | File patterns |
   |----------|-------------|
   | Source code | `src/`, `lib/`, `app/` |
   | Tests | `test/`, `spec/`, `__tests__/`, `*.test.*`, `*.spec.*` |
   | Configuration | `*.config.*`, `.*rc`, `package.json`, `tsconfig.json` |
   | Documentation | `*.md`, `docs/` |
   | Infrastructure | `Dockerfile`, `docker-compose.*`, `.github/`, `terraform/` |
   | Database | `migrations/`, `prisma/`, `*.sql` |

2. **Identify high-risk areas.** Flag files that need careful review:

   | Risk indicator | Why it matters |
   |---------------|---------------|
   | Auth or security files | Permission and access control changes |
   | Database migrations | Schema changes are hard to reverse |
   | API route definitions | Contract changes affect consumers |
   | Shared utilities or core modules | High blast radius |
   | Environment or config changes | Deployment impact |
   | Files with > 200 lines changed | Large diffs are harder to review |

3. **Summarize the diff.** Read the actual diff to understand:
   - What behavior changed.
   - What was added versus modified versus removed.
   - Whether tests cover the changes.

### 3. Suggest Reviewers

For each changed file, find the most frequent contributors:

```bash
git log --format='%an' --since='6 months ago' -- <file> | sort | uniq -c | sort -rn | head -3
```

1. **Aggregate across all files.** Count how many changed files each contributor has history with.

2. **Rank by coverage.** The best reviewer is the person with history across the most changed files.

3. **Exclude the PR author.** Never suggest the author as a reviewer.

4. **Present top 3 suggestions:**

   | Reviewer | Files with history | Coverage |
   |----------|--------------------|----------|
   | Alice | 8 of 12 | 67% |
   | Bob | 5 of 12 | 42% |
   | Carol | 3 of 12 | 25% |

### 4. Generate Summary

If the PR description is empty or under 50 characters, generate a reviewer-friendly description following the format in `../../rules/git-workflow.md`:

- **What:** one paragraph explaining what changed and why.
- **How:** key implementation decisions and trade-offs.
- **Testing:** how changes were verified.
- **Breaking changes:** if any, with migration steps.

### 5. Output

Present the full summary:

1. **PR title and metadata.** Title, author, base branch, head branch, labels.

2. **Change summary.** Categorized file list with line counts.

3. **Risk areas.** Flagged files with explanations.

4. **Test coverage.** Whether tests were added or modified for the changes.

5. **Suggested reviewers.** Top 3 with coverage percentages.

6. **Generated description.** If the existing description was thin, provide the generated one and offer to update the PR:
   ```bash
   GH_TOKEN=$(gh auth token --user <account>) gh pr edit <number> --body-file /tmp/pr-body.md
   ```

## Rules

- Account token prefixing is mandatory for all `gh` commands per `../../rules/github-accounts.md`.
- Never auto-update the PR description without asking. Always present the generated text and let the user decide.
- Reviewer suggestions are based on git history, not organizational hierarchy. State this in the output.
- When the PR has fewer than 3 potential reviewers from git history, show however many are available. Do not pad with guesses.
- All timestamps in GMT.
- Read the actual diff, not just the file list. A file list without context produces shallow summaries.

## Related Skills

- `/review` -- Detailed code review of the PR's changes.
- `/ship pr` -- Create or update a pull request.
- `/ship checks` -- Monitor CI status for the PR.

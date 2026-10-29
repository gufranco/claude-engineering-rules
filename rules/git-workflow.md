# Git Workflow

Conventional commits, a full local quality gate before every commit, one push per task, and CI watched until green with zero annotations.

- Commit format `<type>(<scope>): <subject>`. Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- Subject: imperative, lowercase start, no period, max 50 characters including type and scope. Drop the scope when it does not fit. Measure the length in a call before `git commit`, never by eye, and pass the subject to `-m` as a literal.
- Body wraps at 72 and explains what and why. Footer: `BREAKING CHANGE:`, `Fixes #123`. Optional trailers `Rejected: <alt> | <reason>`, `Constraint:`, `Risk:`.
- Never add AI attribution or `Co-authored-by` lines for any AI. Never write phase-N markers, plan or spec paths, or process narration.
- Branches: `<type>/<ticket-id>-<description>`.
- Before every commit or push, in order: format, lint, type check, full test suite, build. Show output. Rerun if code changed.
- Lint does not imply format: run `prettier --check` separately, over the whole project as CI does: `prettier --write .` then `prettier --check .`.
- Schema changes: push to dev and test DBs, `prisma generate`, full suite. Env var changes update `.env.example`, `.env.test`, CI, and Compose.
- Push once, at the end of the task, after all gates pass. Batch CI fixes into one push. Subagents never push.
- One task, one pull request per repository. A follow-up from the same delivery is cherry-picked onto the open pull request's branch, its title and body updated to name every tracker key; an extra pull request is closed without a comment.
- CI jobs run on the newest GA Ubuntu LTS label, never macOS or a `-latest` label; `step-security/harden-runner` comes first; `actions/*` on tags, third-party actions on full SHAs; a `push` or `pull_request` workflow cancels superseded runs; CI calls the local gate's Makefile targets.
- After push: cancel superseded runs, follow the latest to completion, fix every annotation and deprecation warning. Check `gh api rate_limit` before polling; poll a one-shot `gh run view <id>` at multi-minute intervals.
- If CI does not start, check `gh pr view --json mergeable,mergeableState`; `dirty` means conflicts.
- Run `actionlint`, `yamllint`, and `shellcheck` before committing CI files.
- Never hard-wrap PR, issue, or review-reply bodies. One line per paragraph; 72-column wrap applies only to commit bodies.
- PR description: What, How, Evidence as a before and after, with high-resolution `Before:` and `After:` screenshots attached for any visible change, Merge Danger naming a one-way or two-way door and the blast radius, Breaking changes. Identify the base branch from git; rebase a never-pushed branch before opening, and merge the base into a pushed one only on conflict.
- Never use `--delete-branch` on the first merge of a dual-base PR.
- Pushing to `main`, `master`, or `develop` is blocked. Solo repos listed in the machine-local `solo-repos.txt`, copied from [`solo-repos.example.txt`](../solo-repos.example.txt), are exempt. Never list a repo with reviewers.
- Before rebasing, and before believing any divergence or a push 403, run `git rev-parse --is-shallow-repository`; if `true`, `git fetch --unshallow`. Never trust `git merge-base` on a shallow clone.
- Never force push or amend pushed commits; roll back with `git revert`.
- Your migrations must carry the latest timestamps, rechecked after rebase, and be idempotent with `IF NOT EXISTS` and `IF EXISTS`.
- Never commit `dist/`, `build/`, `.next/`, `out/`, `coverage/`, `node_modules/`. Audit with `git -c core.excludesFile=/dev/null status --porcelain -uall`.
- Before pushing new files, list `git status --porcelain --ignored -- <source dirs>`; a source file marked `!!` was dropped by an ignore rule, often the global one. Rename it or add a negation, then gate on a `git clone` of the commit, never a copy of the working tree.

Full rule, examples, and rationale: [`standards/git-workflow.md`](../standards/git-workflow.md). Read it before writing a commit or PR, diagnosing CI, resolving conflicts, or writing a CHANGELOG.

## Enforcement

Enforced by: [`hooks/bulk-resolve-blocker.py`](../hooks/bulk-resolve-blocker.py).
Enforced by: [`hooks/conventional-commits.py`](../hooks/conventional-commits.py).
Enforced by: [`hooks/doc-sync-guard.py`](../hooks/doc-sync-guard.py).
Enforced by: [`hooks/force-push-during-review.py`](../hooks/force-push-during-review.py).
Enforced by: [`hooks/gh-run-watch-blocker.py`](../hooks/gh-run-watch-blocker.py).
Enforced by: [`hooks/gh-short-sha-guard.py`](../hooks/gh-short-sha-guard.py).
Enforced by: [`hooks/git-author-guard.py`](../hooks/git-author-guard.py).
Enforced by: [`hooks/large-file-blocker.py`](../hooks/large-file-blocker.py).
Enforced by: [`hooks/review-state-guard.py`](../hooks/review-state-guard.py).
Enforced by: [`hooks/workflow-guard.py`](../hooks/workflow-guard.py).
Enforced by: [`hooks/pr-comment-discipline.py`](../hooks/pr-comment-discipline.py).

## Provenance

Added 2026-03-06, recurrence not recorded. Origin: not recorded at creation. Amended 2026-10-14, recurrence 5 in one session: subjects judged by eye overran the 50-character limit and each cost a blocked commit, so the core now requires measuring the length first. Amended again 2026-10-14, recurrence 3 since 2026-09-30: CI watchers filtered `gh run list --commit` by a short SHA, got zero runs with exit 0, and reported done; [`hooks/gh-short-sha-guard.py`](../hooks/gh-short-sha-guard.py) now blocks it. Amended 2026-10-28, recurrence 3 since 2026-09-27: the global ignore file's `*.patch` and `*.log.*` rules silently left needed files out of commits in fdswriteunlock, DoomNG and madoguchi, and each time a build from the working tree passed while the clean CI checkout failed, so the core now requires the ignored-file check and a clone-based gate before pushing new files. Amended 2026-10-29, `single-incident`, by direct user instruction: tsos-tech/overwatch #677 carried the schema sync for #671 as a second pull request on 2026-10-28 and was folded in by hand, so a second `gh pr create` for one repository in one session now asks first. Amended 2026-10-29, by direct user instruction given 2026-10-16 and 2026-10-28: the CI defaults bullet, now blocked at write time by [`hooks/workflow-guard.py`](../hooks/workflow-guard.py).

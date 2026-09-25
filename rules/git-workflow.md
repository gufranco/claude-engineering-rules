# Git Workflow

Conventional commits, a full local quality gate before every commit, one push per task, and CI watched until green with zero annotations.

- Commit format `<type>(<scope>): <subject>`. Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- Subject: imperative, lowercase start, no period, max 50 characters including type and scope. Drop the scope when it does not fit.
- Body wraps at 72 and explains what and why. Footer: `BREAKING CHANGE:`, `Fixes #123`. Optional trailers `Rejected: <alt> | <reason>`, `Constraint:`, `Risk:`.
- Never add AI attribution or `Co-authored-by` lines for any AI. Never write phase-N markers, plan or spec paths, or process narration.
- Branches: `<type>/<ticket-id>-<description>`.
- Before every commit or push, in order: format, lint, type check, full test suite, build. Show output. Rerun if code changed.
- Lint does not imply format: run `prettier --check` separately, over the whole project as CI does: `prettier --write .` then `prettier --check .`.
- Schema changes: push to dev and test DBs, `prisma generate`, full suite. Env var changes update `.env.example`, `.env.test`, CI, and Compose.
- Push once, at the end of the task, after all gates pass. Batch CI fixes into one push. Subagents never push.
- After push: cancel superseded runs, watch the latest, fix every annotation and deprecation warning. Check `gh api rate_limit` before a watcher; below 500 remaining, use one-shot `gh run view`. Poll a `queued` run at multi-minute intervals.
- If CI does not start, check `gh pr view --json mergeable,mergeableState`; `dirty` means conflicts.
- Run `actionlint`, `yamllint`, and `shellcheck` before committing CI files.
- Never hard-wrap PR, issue, or review-reply bodies. One line per paragraph; 72-column wrap applies only to commit bodies.
- PR description: What, How, Testing, Breaking changes. Identify the base branch from git and rebase before opening.
- Never use `--delete-branch` on the first merge of a dual-base PR.
- Pushing to `main`, `master`, or `develop` is blocked. Solo repos listed in the machine-local `solo-repos.txt`, copied from [`solo-repos.example.txt`](../solo-repos.example.txt), are exempt. Never list a repo with reviewers.
- Before rebasing, and before believing any divergence or a push 403, run `git rev-parse --is-shallow-repository`; if `true`, `git fetch --unshallow`. Never trust `git merge-base` on a shallow clone.
- Never force push or amend pushed commits; roll back with `git revert`.
- Your migrations must carry the latest timestamps, rechecked after rebase, and be idempotent with `IF NOT EXISTS` and `IF EXISTS`.
- Never commit `dist/`, `build/`, `.next/`, `out/`, `coverage/`, `node_modules/`. Audit with `git -c core.excludesFile=/dev/null status --porcelain -uall`.

Full rule, examples, and rationale: [`standards/git-workflow.md`](../standards/git-workflow.md). Read it before writing a commit or PR, diagnosing CI, resolving conflicts, or writing a CHANGELOG.

## Enforcement

Enforced by: [`hooks/bulk-resolve-blocker.py`](../hooks/bulk-resolve-blocker.py).
Enforced by: [`hooks/conventional-commits.py`](../hooks/conventional-commits.py).
Enforced by: [`hooks/doc-sync-guard.py`](../hooks/doc-sync-guard.py).
Enforced by: [`hooks/force-push-during-review.py`](../hooks/force-push-during-review.py).
Enforced by: [`hooks/gh-run-watch-blocker.py`](../hooks/gh-run-watch-blocker.py).
Enforced by: [`hooks/git-author-guard.py`](../hooks/git-author-guard.py).
Enforced by: [`hooks/large-file-blocker.py`](../hooks/large-file-blocker.py).
Enforced by: [`hooks/review-state-guard.py`](../hooks/review-state-guard.py).

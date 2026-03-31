---
name: deploy
description: Merge PRs, verify deployments, and monitor post-deploy health. Subcommands: land (default), canary. Extends the delivery pipeline past /ship by handling merge, deployment verification, and post-deploy monitoring. Use when user says "deploy", "merge and deploy", "land this PR", "canary", "post-deploy check", "verify deployment", or wants to take a shipped PR through to production. Do NOT use for creating PRs (use /ship pr), running tests (use /test), or CI diagnosis (use /ship checks).
---

Post-merge deployment and monitoring skill. Picks up where `/ship` leaves off: merging the PR, verifying the deployment succeeds, and monitoring production health afterward.

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/deploy` or `/deploy land` | Merge PR and verify deployment (default) |
| `/deploy canary` | Post-deploy monitoring for errors and regressions |

If no subcommand is given, default to `land`.

---

## land

Merge a PR, wait for the deployment pipeline, and verify production health.

### When to use

- After `/ship pr` created a PR and CI is green.
- When a PR is approved and ready to merge.

### Arguments

- No arguments: detect the PR for the current branch.
- PR number or URL: target a specific PR.
- `--squash`: squash merge (default).
- `--merge`: create a merge commit instead.
- `--no-delete`: keep the branch after merge.

### Steps

1. **Identify the PR.** If no argument, find the PR for the current branch:
   ```
   gh pr view --json number,state,reviewDecision,statusCheckRollup
   ```
   If no `gh` is available, try `glab`. Prefix with the appropriate token per `../../rules/github-accounts.md` or `../../rules/gitlab-accounts.md`.

2. **Pre-merge checks.** Verify all conditions are met:

   | Condition | How to check | Blocker? |
   |-----------|-------------|----------|
   | CI is green | `statusCheckRollup` all passing | Yes |
   | PR is approved | `reviewDecision` is APPROVED | Yes |
   | No merge conflicts | `mergeable` is true | Yes |
   | Branch is up to date | Compare with base branch HEAD | Warning only |

   If any blocker condition fails, stop and report the issue. Do not merge.

3. **Merge the PR.** Default to squash merge:
   ```
   gh pr merge <number> --squash --delete-branch
   ```
   If `--no-delete` is passed, omit `--delete-branch`.
   If this is a dual-base PR (same change targeting two branches), omit `--delete-branch` per `../../rules/git-workflow.md`.

4. **Wait for deployment.** Detect the deployment mechanism:

   | Signal | Platform | How to monitor |
   |--------|---------|---------------|
   | `.github/workflows/` with deploy job | GitHub Actions | `gh run list --branch main --limit 1 --json databaseId,status` then `gh run watch` |
   | Vercel project | Vercel | Check Vercel MCP or `vercel ls --limit 1` |
   | Railway, Render, Fly | PaaS | Suggest user check the dashboard |
   | Manual deploy | Any | Ask user to trigger and confirm |

   If no deployment mechanism is detected, ask the user how deployments work.

5. **Verify production health.** After deployment completes:
   - If a health endpoint is known (from project docs or user input), `curl` it and verify 200.
   - If the project has a public URL, verify it loads.
   - Check for new error reports if monitoring is configured (Sentry MCP, etc.).
   - Report the deployment result.

6. **Switch to local main.** After successful deployment:
   ```
   git checkout main && git pull origin main
   ```

### Output

```
## Deployment Summary

**PR:** #<number> - <title>
**Merged:** <timestamp GMT>
**Method:** squash / merge commit
**Branch deleted:** yes / no

### Deployment
**Platform:** <detected platform>
**Status:** success / pending / failed
**URL:** <production URL if known>

### Health Check
**Endpoint:** <URL checked>
**Status:** <HTTP status code>
**Errors:** none / <error details>
```

---

## canary

Monitor a recently deployed change for errors, performance regressions, and unexpected behavior.

### When to use

- Immediately after `/deploy land` succeeds.
- When a deploy happened outside this session and the user wants a health check.
- When monitoring a risky change in the first minutes after deployment.

### Arguments

- No arguments: monitor for 5 minutes with checks every 60 seconds.
- `--duration <minutes>`: monitor for a custom duration.
- `--url <url>`: target a specific URL for health checks.
- `--baseline`: capture current metrics as the baseline before a deploy (run this first).

### Steps

1. **Establish baseline.** If `--baseline` was passed or no prior baseline exists:
   - Record current error rate from monitoring tools (if accessible).
   - Record response time for key endpoints.
   - Save as the comparison point.

2. **Monitor loop.** For each check interval:
   - Verify the health endpoint returns 200.
   - Check for new errors in monitoring tools (Sentry MCP if available).
   - Compare current response time against baseline.
   - Check browser console for JavaScript errors (if Playwright MCP is available and a frontend URL is known).

3. **Report per interval:**

   | Check | Status |
   |-------|--------|
   | Health endpoint | 200 OK / <error> |
   | New errors | 0 / <count and summary> |
   | Response time | <current> vs <baseline> |
   | Console errors | 0 / <count> |

4. **Final report after monitoring completes:**

   ```
   ## Canary Report

   **Duration:** <N> minutes
   **Intervals:** <count>
   **URL:** <monitored URL>

   ### Health
   **Uptime:** <percentage>
   **Errors detected:** <count>

   ### Performance
   **Response time (baseline):** <value>
   **Response time (current):** <value>
   **Delta:** <percentage change>

   ### Verdict
   <CLEAN: no issues detected / WARNING: <issues found>>
   ```

5. **If issues detected:** suggest rollback steps:
   - `git revert <merge-commit> && git push`
   - Or revert via the platform's rollback mechanism.

## Rules

- Never merge a PR with failing CI checks. No exceptions.
- Never merge without approval unless the user explicitly requests it.
- Prefix every `gh` or `glab` command with the appropriate token per `../../rules/github-accounts.md` or `../../rules/gitlab-accounts.md`.
- All timestamps in GMT.
- Canary monitoring is non-blocking: report findings, do not auto-rollback without user confirmation.
- If rate limits are a concern for monitoring, use one-shot checks instead of continuous polling per `../../rules/git-workflow.md`.
- Never access production databases or infrastructure directly. Use health endpoints and monitoring tool APIs only.

## Related skills

- `/ship pr` -- Create the PR that this skill merges.
- `/ship checks` -- Diagnose CI failures before merging.
- `/incident` -- Document the incident if the deploy causes problems.
- `/investigate` -- Debug issues found during canary monitoring.

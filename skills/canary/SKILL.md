---
name: canary
description: Post-deploy monitoring as a standalone skill. Checks HTTP status, response time, and response body validity at regular intervals, compares against a pre-deploy baseline, and produces a clean deploy report or a regression report with timestamps and evidence. Use when user says "canary", "monitor deploy", "watch production", "post-deploy check", "health monitor", or wants to monitor a URL or service after deployment. Do NOT use for merging PRs (use /deploy land), CI checks (use /ship checks), or incident reports (use /incident).
sensitive: true
---
Standalone post-deploy monitoring skill. Polls a target URL at regular intervals, checks for regressions against a baseline, and produces a report with evidence.

## Invocation

| Invocation | Action |
|-----------|--------|
| `/canary` | Monitor the project's production URL for 10 minutes |
| `/canary <duration>` | Monitor for a custom duration, e.g., `5m`, `30m`, `1h` |
| `/canary <url>` | Monitor a specific URL for 10 minutes |
| `/canary <url> <duration>` | Monitor a specific URL for a custom duration |
| `/canary baseline` | Capture current metrics as the pre-deploy baseline |

---

## Steps

1. **Determine the target.** Identify what to monitor:
   - If a URL argument is provided, use it directly.
   - If no URL: check the project for a production URL in `package.json` homepage, `vercel.json`, `fly.toml`, `render.yaml`, `CLAUDE.md`, or `README.md`.
   - If no URL is found, ask the user.

2. **Determine the duration.** Parse the duration argument:
   - Default: 10 minutes.
   - Accepted formats: `5m`, `30m`, `1h`, `90s`.
   - Check interval: every 30 seconds.
   - Calculate total check count: duration / 30 seconds.

3. **Load baseline.** If a baseline file exists at `.canary-baseline.json` in the project root:
   - Read the baseline: HTTP status, average response time, response body hash or key fields.
   - Report that a baseline is loaded and when it was captured.
   - If no baseline exists, the first check becomes the baseline for this run.

4. **Baseline capture mode.** If `/canary baseline` is invoked:
   - Run 5 checks at 10-second intervals.
   - Record: HTTP status, average response time, response body hash, content-type, response size.
   - Save to `.canary-baseline.json` in the project root.
   - Report the baseline and exit.

5. **Monitoring loop.** For each check interval:
   - Send an HTTP GET request: `curl -s -o /dev/null -w "%{http_code} %{time_total} %{size_download}" <url>`
   - Record: timestamp, HTTP status code, response time in milliseconds, response size.
   - If the baseline exists, compare:

     | Metric | Regression threshold |
     |--------|---------------------|
     | HTTP status | Any non-2xx when baseline is 2xx |
     | Response time | More than 2x the baseline average |
     | Response size | More than 50% change from baseline |

   - If a regression is detected, log it immediately with the timestamp and evidence.

6. **On regression detected.** When a check fails the threshold:
   - Log the finding with timestamp, expected value, actual value.
   - If 3 consecutive checks show a regression, escalate: suggest a rollback command.
   - Rollback suggestion: `git revert <last-merge-commit> && git push` or the platform's native rollback mechanism.
   - If a webhook URL is configured in `.canary-baseline.json` under `webhook`, send a POST with the regression payload.

7. **Final report.** After the monitoring duration completes:

### Output

```
## Canary Report

**Target:** <URL>
**Duration:** <actual duration>
**Checks:** <count completed>/<count planned>
**Baseline:** <loaded from file / first-run baseline / none>

### Health Summary
| Metric | Baseline | Current avg | Status |
|--------|----------|-------------|--------|
| HTTP status | <code> | <code> | OK / REGRESSION |
| Response time | <ms> | <ms> | OK / REGRESSION |
| Response size | <bytes> | <bytes> | OK / REGRESSION |

### Check Log
| # | Timestamp (GMT) | Status | Response time | Size | Notes |
|---|----------------|--------|--------------|------|-------|
| 1 | <HH:MM:SS> | <code> | <ms> | <bytes> | |
| 2 | <HH:MM:SS> | <code> | <ms> | <bytes> | REGRESSION: response time 2.5x baseline |

### Regressions
<List of all regressions detected with timestamps and evidence,
or "No regressions detected.">

### Verdict
<CLEAN DEPLOY: all checks passed within thresholds>
<REGRESSION DETECTED: N checks exceeded thresholds, rollback recommended>

### Suggested Rollback
(Only if regressions detected)
git revert <commit> && git push
```

## Configuration

The `.canary-baseline.json` file stores baseline metrics and optional configuration:

```json
{
  "url": "https://example.com",
  "captured": "2026-04-04T12:00:00Z",
  "status": 200,
  "avgResponseTime": 245,
  "avgResponseSize": 15234,
  "bodyHash": "sha256:abc123...",
  "webhook": "https://hooks.slack.com/services/..."
}
```

## Rules

- All timestamps in GMT.
- Never auto-rollback without user confirmation. Report the regression and suggest the command.
- Rate limit awareness: 30-second intervals are the minimum. Never poll more frequently.
- If `curl` is not available, ask the user to install it. Do not fall back to other tools without confirmation.
- The monitoring loop is blocking. Report progress inline as each check completes.
- If the target URL requires authentication, ask the user for headers or tokens. Never guess credentials.
- Do not store authentication tokens in `.canary-baseline.json`. Store them in environment variables only.
- Prefix every `gh` or `glab` command with the appropriate token per `../../rules/github-accounts.md` or `../../rules/gitlab-accounts.md`.

## Related skills

- `/deploy land` -- Merge a PR and trigger deployment before monitoring.
- `/deploy canary` -- Alternative canary implementation integrated with the deploy flow.
- `/incident` -- Document an incident if regressions are confirmed.
- `/investigate` -- Debug the root cause of a regression.

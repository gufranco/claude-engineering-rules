---
name: weekly
description: Sprint or week retrospective with delivery metrics. Aggregates commits, PRs, and issues from the past N days, calculates velocity, identifies patterns, and produces a summary for standup or sprint review. Use when user says "weekly", "sprint summary", "what did we ship", "weekly retro", "velocity", "sprint review", "week in review", or wants a summary of team delivery over a period. Do NOT use for daily standup (use /morning), session-level retrospective (use /retro), or incident reports (use /incident).
---

Sprint or week retrospective that aggregates delivery data from git and the issue tracker, calculates velocity metrics, and produces a structured summary. Covers commits, merged PRs, closed issues, lines changed, and carry-over items. Groups work by type and identifies patterns in delivery cadence.

## When to use

- At the end of a sprint or week to summarize what shipped.
- Before a sprint review or retro meeting to gather data.
- When a manager or lead asks "what did we ship this week?"
- To track velocity trends across multiple periods.

## When NOT to use

- For daily standup prep. Use `/morning --standup` instead.
- For session-level corrections and preferences. Use `/retro` instead.
- For incident postmortems. Use `/incident` instead.
- For a single PR summary. Use `/pr-summary` instead.

## Arguments

This skill accepts optional arguments after `/weekly`:

- No arguments: summarize the last 7 days.
- `<N>`: summarize the last N days. Example: `/weekly 14` for a two-week period.
- `--sprint`: attempt to detect sprint boundaries from the issue tracker and use those dates instead of a fixed day count.

## Steps

1. **Determine the time window.** Parse arguments to set the start date. Default is 7 days. If `--sprint` was passed, query the issue tracker for the current or most recent sprint and extract its start and end dates. Fall back to 7 days if sprint detection fails.

2. **Gather commits.** Run `git log --since="<start-date>" --oneline --format="%h %s (%an, %ar)" --all`. Count total commits. Parse conventional commit prefixes to classify each commit by type.

3. **Gather merged PRs.** Detect the platform from the remote URL.
   - GitHub: `GH_TOKEN=$(gh auth token --user <account>) gh pr list --state merged --search "merged:>YYYY-MM-DD" --json number,title,author,mergedAt,additions,deletions,url`
   - GitLab: `GITLAB_TOKEN=<token> GITLAB_HOST=<host> glab mr list --state merged`
   - For each PR, extract: number, title, author, merge date, lines added, lines removed.

4. **Gather closed issues.**
   - GitHub: `GH_TOKEN=$(gh auth token --user <account>) gh issue list --state closed --search "closed:>YYYY-MM-DD" --json number,title,closedAt,labels,url`
   - GitLab: `GITLAB_TOKEN=<token> GITLAB_HOST=<host> glab issue list --closed --updated-after YYYY-MM-DD`

5. **Calculate metrics.**
   - Total commits.
   - PRs merged count.
   - Issues closed count.
   - Lines added and removed: `git diff --stat HEAD@{N.days.ago}..HEAD` or sum from PR data.
   - Files changed: `git diff --stat HEAD@{N.days.ago}..HEAD | tail -1`.
   - Average PR size: total lines changed divided by PRs merged.
   - Average time to merge: mean of merge date minus creation date across merged PRs.

6. **Group by type.** Classify commits and PRs using conventional commit prefixes:
   - Features: `feat` commits and PRs.
   - Bug fixes: `fix` commits and PRs.
   - Maintenance: `chore`, `refactor`, `docs`, `style`, `build`, `ci` commits and PRs.
   - Tests: `test` commits and PRs.
   - Performance: `perf` commits and PRs.

7. **Identify patterns.**
   - Busiest days: count commits per day, highlight the peak.
   - Largest PRs: top 3 PRs by lines changed.
   - Recurring areas: list the top 5 most-changed directories or modules.
   - Commit distribution by author if multiple contributors exist.

8. **List carry-over items.**
   - Open PRs created before the period that are still open.
   - Issues assigned during the period that were not closed.
   - Draft PRs older than 7 days.

9. **Present the summary.** Use this format:

   ```
   ## Weekly Summary — <start-date> to <end-date>

   <One paragraph summarizing the period: what the focus was, what shipped, any notable events.>

   ### Metrics

   | Metric | Value |
   |--------|-------|
   | Commits | N |
   | PRs merged | N |
   | Issues closed | N |
   | Lines added | +N |
   | Lines removed | -N |
   | Files changed | N |
   | Avg PR size | N lines |
   | Avg time to merge | N days |

   ### What shipped

   **Features**
   - PR #N: title (author)

   **Bug fixes**
   - PR #N: title (author)

   **Maintenance**
   - PR #N: title (author)

   **Tests**
   - PR #N: title (author)

   ### Carry-over

   - PR #N: title — open for N days, status
   - Issue #N: title — assigned to X, not closed

   ### Patterns

   - Busiest day: Wednesday with N commits
   - Largest PR: #N with +X/-Y lines
   - Most-changed areas: src/auth (N files), src/api (N files)
   ```

10. **Format for sharing.** Use flat prose, bold labels, and bullet lists so the output survives pasting into Slack or team docs without losing structure. No Markdown tables in the shareable version.

## Rules

- Use git and CLI tools for all data. Never estimate or guess what was shipped.
- Always include carry-over items. Unfinished work is as important as finished work for sprint planning.
- Always prefix `gh` commands with the correct `GH_TOKEN` per the github-accounts rule.
- Always prefix `glab` commands with `GITLAB_TOKEN` and `GITLAB_HOST` per the gitlab-accounts rule.
- Show times in relative format when listing individual items.
- When multiple authors contributed, attribute work to the correct author.
- If the issue tracker or PR tool is unavailable, fall back to git-only metrics and note the limitation.
- Never include AI attribution markers in the output.

## Related skills

- `/morning` - Daily standup dashboard with open PRs and pending reviews.
- `/retro` - Session-level retrospective that extracts corrections and preferences.
- `/incident` - Incident postmortem with timeline and root cause analysis.
- `/pr-summary` - Summarize a single PR with reviewer suggestions.
- `/session-log` - Activity log for the current session.

---
name: session-log
description: Session activity logger for handoff and standup. Shows what was done in the current session, including files changed, tests run, commits made, and decisions taken. Use when user says "session log", "what did we do", "session summary", "handoff notes", "standup notes", "export session", or wants a summary of current session activity for handoff or standup prep. Do NOT use for retrospectives (use /retro), checkpoints (use /checkpoint), or morning standup dashboard (use /morning).
---

Session activity logger that builds a summary of what happened in the current session. Useful for handoff between developers, standup preparation, and session documentation.

## Invocation

| Invocation | Action |
|-----------|--------|
| `/session-log` | Display session summary in the conversation |
| `/session-log export` | Export session summary as a markdown file |

---

## Steps

1. **Gather git activity.** Collect commits made during this session:
   - Run `git log --oneline --since="<session start or today>"` to find recent commits.
   - If no commits exist since today, check the last 24 hours.
   - For each commit: hash, message, files changed.

2. **Gather file changes.** Identify all files modified in the session:
   - Run `git diff --name-status` for uncommitted changes.
   - Run `git diff --cached --name-status` for staged changes.
   - Categorize: added, modified, deleted, renamed.

3. **Gather test activity.** Check if tests were run during the session:
   - Look for test output in the conversation history.
   - Summarize: test suite name, pass/fail counts, coverage if reported.

4. **Gather decisions.** Scan the conversation for decisions made during the session:
   - Architecture choices.
   - Trade-offs discussed and resolved.
   - Scope changes agreed upon.
   - Rejected approaches with reasons.

5. **Identify next steps.** Based on the session context:
   - What remains unfinished?
   - What follow-up tasks were identified?
   - What blockers exist?

6. **Format the output.** Compile into a structured summary.

### Output

```
## Session Log

**Date:** <timestamp GMT>
**Duration:** <approximate>
**Branch:** <current branch>

### Commits
| Hash | Message |
|------|---------|
| <short hash> | <commit message> |

### Files Changed
| Status | File |
|--------|------|
| M | <path> |
| A | <path> |
| D | <path> |

### Tests
| Suite | Passed | Failed | Coverage |
|-------|--------|--------|----------|
| <name> | <count> | <count> | <percentage or N/A> |

### Decisions
1. <Decision made and rationale>
2. <Decision made and rationale>

### Next Steps
- [ ] <Remaining task>
- [ ] <Follow-up identified>
- [ ] <Blocker to resolve>
```

### Export mode

When `/session-log export` is invoked:
- Write the output to a file named `session-log-<YYYY-MM-DD-HHMM>.md` in the project root.
- Confirm the file path after writing.

## Rules

- All timestamps in GMT.
- Do not fabricate session activity. Only include what actually happened based on git history and conversation context.
- Decisions must reflect what was actually discussed, not inferred preferences.
- Keep each section concise. The reader needs a quick overview, not a transcript.
- If no activity exists in a section, state "None this session" instead of omitting the section.

## Related skills

- `/retro` -- Deeper retrospective that persists learnings as config.
- `/checkpoint` -- Save working state for cross-session resumption.
- `/morning` -- Start-of-day dashboard with pending work.
- `/ship commit` -- Commit changes identified in the session log.

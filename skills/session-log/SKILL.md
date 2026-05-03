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

## Session Boundary Heuristics

A session boundary is a moment where short-term context should be flushed to long-term memory before it is lost to compaction or session end. The skill writes a memory entry whenever a boundary is detected, instead of waiting for an explicit save.

| Trigger | Detection signal | Action |
|---------|-----------------|--------|
| Idle gap | More than 30 minutes between the last assistant turn and the next user turn | Write a project memory summarizing the in-progress task and any open decisions |
| Topic shift | The user's new prompt has no shared keywords with the previous 5 turns and introduces a different domain (different repo, feature area, or skill family) | Write a project memory closing out the previous topic |
| Pre-compaction | A `compact-context-saver` event fires or the assistant detects context near the 60% threshold | Write a feedback memory if any corrections happened, plus a project memory of the current task state |
| Explicit handoff | The user says "I'll be back later", "save this for tomorrow", "let's pick up next session", or equivalent in any language | Write both a project memory and a checkpoint reference |
| Task completion | A multi-step task ends with verified evidence (build green, PR merged, deploy confirmed) | Write a project memory marking the task done with the final state |

When a boundary fires:

1. Generate a one-paragraph summary of the current task state, open decisions, and unresolved questions.
2. Save as a project memory using the auto-memory format from `~/.claude/CLAUDE.md`.
3. Update `MEMORY.md` to point to the new entry.
4. If the trigger was topic shift or idle gap, do not interrupt the user with a status message: write silently.
5. If the trigger was explicit handoff or pre-compaction, briefly tell the user the memory was saved and where.

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

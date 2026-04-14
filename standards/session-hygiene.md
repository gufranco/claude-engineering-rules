# Session Hygiene

## Session Naming

Name every session with the `-n` flag. Unnamed sessions are impossible to find later.

```bash
claude -n "feat/quote-pdf-export"
claude -n "bugfix/dispatch-timezone"
claude -n "refactor/auth-hexagonal"
```

Use the same naming convention as branches: `type/short-description`.

## Checkpoint Before Risky Operations

Before any operation that changes significant state, create a mental checkpoint by noting:

- Current branch and last commit hash
- Files modified but not committed
- Tests that were passing before the operation

Risky operations include: rebasing, resetting, deleting files, running migrations, and bulk refactors.

## Safe Experimentation with /rewind

Use `/rewind` as a safe experimentation point. Before trying an uncertain approach:

1. Note the current conversation state.
2. Try the approach.
3. If it fails, `/rewind` to the checkpoint and try a different path.

This prevents context pollution from failed experiments.

## Multi-Session Awareness

When working across multiple sessions, verify at the start of each session:

| Check | How |
|-------|-----|
| Correct project directory | `pwd` and verify |
| Correct branch | `git branch --show-current` |
| Clean working tree | `git status` |
| No stale changes from another session | Review uncommitted modifications |
| Correct environment | Check `.env` or active config |

Never assume the environment matches the last session. Another session or manual work may have changed state.

## Proactive Compaction

Compact at 60% context usage, not when the session is already degraded. Signs that compaction is overdue:

- Re-reading files that were read earlier in the session
- Forgetting decisions made earlier
- Producing output that contradicts earlier output
- Asking questions that were already answered

## Plan Re-reading

Before each implementation phase, re-read the plan:

1. At the start of the session, read `plan.md` from the spec folder.
2. Every 50 tool calls, re-read the plan to prevent drift.
3. After compaction, re-read the plan immediately.
4. Before declaring a phase complete, verify against the plan's acceptance criteria.

## Context Snapshot Before Long Operations

Before operations that consume many tool calls, like large refactors or multi-file implementations, snapshot the context:

- List all files to be modified
- State the expected outcome for each file
- Note which tests must pass after the operation

This snapshot survives context degradation and serves as a self-correction reference.

## Session Boundaries

| Signal | Action |
|--------|--------|
| Task complete, all gates passed | End the session cleanly |
| Context at 60% | Compact proactively |
| Context at 80% | Compact immediately, finish current step, avoid new work |
| Context at 95% | Stop. Commit progress. Start a new session with a summary of remaining work |
| Switching projects | End the session. Start a new one with the correct project context |

## End-of-Session Checklist

Before ending a session:

1. All modified files are committed or explicitly noted as work-in-progress.
2. Current branch and task state are recorded.
3. Any remaining work is documented for the next session.
4. No temp files, debug logs, or diagnostic code left in the working tree.

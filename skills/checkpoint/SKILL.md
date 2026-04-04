---
name: checkpoint
description: Save and resume working state across sessions. Subcommands: save, resume, list. Captures git state, decisions made, remaining work, and modified files so a new session can pick up where the last one left off. Use when user says "checkpoint", "save progress", "save state", "resume", "pick up where I left off", or wants to preserve session context. Do NOT use for git commits (use /ship commit), retrospectives (use /retro), or planning (use /plan).
---

Persist working state to disk so a future session can restore full context without the user re-explaining everything.

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/checkpoint save` | Capture current state to a checkpoint file |
| `/checkpoint resume` | Restore context from the most recent checkpoint |
| `/checkpoint resume <id>` | Restore context from a specific checkpoint |
| `/checkpoint list` | Show all available checkpoints |
| `/checkpoint` | Default to `save` |

## Storage

Checkpoints are stored in `~/.claude/checkpoints/`. Each file is named `<session-id>.md` where session-id is a timestamp-based identifier: `YYYYMMDD-HHmmss`.

## Process

### Save

1. **Gather git state.** Run these in parallel:
   - `git branch --show-current` to capture the active branch.
   - `git log --oneline -5` to capture recent commits.
   - `git status --short` to capture uncommitted changes.
   - `git diff --stat` to capture the scope of modifications.

2. **Gather session context.** From the current conversation, extract:
   - The current task description.
   - Decisions made during the session, with rationale.
   - Files modified or created.
   - Files read that are relevant to the task.
   - Any blockers or open questions.
   - Next steps remaining.

3. **Write the checkpoint file.** Create `~/.claude/checkpoints/<session-id>.md` with this structure:

   ```markdown
   # Checkpoint: <session-id>

   **Saved:** <GMT timestamp>
   **Branch:** <branch name>
   **Project:** <repo root path>

   ## Task

   <current task description>

   ## Decisions

   - <decision 1>: <rationale>
   - <decision 2>: <rationale>

   ## Modified Files

   - <file path 1>
   - <file path 2>

   ## Recent Commits

   <output of git log --oneline -5>

   ## Uncommitted Changes

   <output of git status --short>

   ## Next Steps

   1. <remaining step 1>
   2. <remaining step 2>

   ## Blockers

   - <blocker or open question, if any>
   ```

4. **Confirm.** State the checkpoint ID and file path to the user.

### Resume

1. **Find the checkpoint.** If no ID is given, use the most recent file in `~/.claude/checkpoints/` sorted by filename. If an ID is given, read that specific file.

2. **Read the checkpoint file.** Parse all sections.

3. **Verify the environment.** Run these in parallel:
   - `git branch --show-current` to confirm the branch matches.
   - `git status --short` to see if files have changed since the checkpoint.
   - Verify the project directory matches.

4. **Output the context.** Present the full checkpoint contents to re-ground the session:
   - State the task.
   - List decisions already made.
   - List modified files.
   - State remaining next steps.
   - Flag any discrepancies between the checkpoint and the current git state.

5. **Proceed.** Ask the user which next step to start with, or continue from the first remaining step if the instruction is clear.

### List

1. **Read the checkpoints directory.** List all `.md` files in `~/.claude/checkpoints/`, sorted by name descending.

2. **Display a summary table:**

   | ID | Saved | Branch | Task |
   |----|-------|--------|------|

   Extract the branch and task from each file's header section.

## Rules

- Checkpoints are informational snapshots, not git operations. They never commit, stash, or modify the working tree.
- Timestamps use GMT, never local timezone.
- The checkpoint file must be self-contained. A reader with no prior context must understand the full state from the file alone.
- On resume, if the branch has diverged significantly from the checkpoint, warn the user before proceeding.
- Never delete checkpoint files automatically. Only `/checkpoint prune` or manual deletion removes them.
- Create the `~/.claude/checkpoints/` directory if it does not exist.

## Related Skills

- `/ship commit` -- Commit changes after resuming and completing work.
- `/retro` -- Run a retrospective after a multi-session task.
- `/plan` -- Create a plan before starting work that checkpoints can reference.

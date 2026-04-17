# Context Management

## Compaction Timing

Compact at 60% context usage, not 95%.

## What to Preserve After Compaction

Every compaction must retain these items. If any is lost, the session is broken.

| Item | Why |
|------|-----|
| List of modified files with absolute paths | Prevents re-reading and conflicting edits |
| Test/lint/build commands already run and their results | Prevents re-running and false confidence |
| Current task description and acceptance criteria | Prevents scope drift |
| User decisions made during the conversation | Prevents re-asking resolved questions |
| Active plan reference, spec folder path if one exists | Prevents diverging from the agreed plan |
| Current branch name and base branch | Prevents commits to the wrong branch |

## Plan Re-reading

Re-read `plan.md` from the spec folder every 50 tool calls.

## Subagent Context Isolation

Every subagent prompt must include:

- File paths relevant to the task, not file contents
- Decisions already made that the agent must respect
- The exact output format expected
- Quality gate commands to run before declaring done

Never send raw file contents, full conversation history, or vague instructions.

## SessionStart Compact Hook

When a session starts with a compacted context from a previous session:

1. Read the list of modified files. Confirm they exist and contain the expected changes.
2. Check the current branch matches the preserved branch name.
3. Re-read the active plan if one exists.
4. Do not trust preserved test results. Re-run if code has changed since.

## Context Budget Awareness

| Pattern | Cost | Alternative |
|---------|------|-------------|
| Reading the same file twice | 2x the tokens | Read once, reference by line numbers |
| Reading entire large files | Thousands of tokens | Use offset and limit to read relevant sections |
| Verbose agent output | Inflates main context | Require structured, minimal output format |
| Spawning 3+ agents concurrently | 3-5x context duplication | Sequence or do inline |

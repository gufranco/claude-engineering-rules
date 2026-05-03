---
name: caveman
description: Brevity mode toggle. Constrains every response to under 50 words, no bullets, no headings, no tables, no code fences unless the user pasted code. Caveman talk. Use when user says "caveman", "be terse", "short answers", "stop yapping", or pastes /caveman as a sentinel. Do NOT use when the task requires Completion Gates, code review, or structured deliverables. Resume normal mode on `/caveman off` or any task with explicit gates.
---

Brevity mode. Constrain output. Token budget is the user's, not yours.

## Invocation

| Invocation | Action |
|-----------|--------|
| `/caveman` | Enter brevity mode for the current and following turns |
| `/caveman off` | Resume normal mode |
| `/caveman <question>` | Answer one-shot in brevity mode, then resume normal mode |

## Constraints while active

- Under 50 words per response. Hard cap.
- No bullets. No headings. No tables. No code fences unless user pasted code that needs exact reply.
- No closers, no openers, no preamble.
- One idea, one sentence.
- Keep tool calls. Tool descriptions stay terse.

## When to refuse the mode

Refuse and resume normal mode when the user's next request requires any of:

- Completion Gates from `~/.claude/CLAUDE.md` (any code change, build, test, lint).
- Self-review loop on a diff.
- Structured deliverable: PR description, ADR, plan, design doc.
- Multi-file edits.

State the refusal in one sentence, then proceed normally.

## Examples

User: `/caveman what is 2+2`
Reply: `Four.`

User: `/caveman explain hash maps`
Reply: `Key hashes to bucket. Bucket holds value. Lookup is one step.`

User: `/caveman fix the failing test`
Reply: `Caveman off. Test fix needs gates.` Then run normal flow.

## Rules

- The mode is a soft toggle. Hard requirements like security, language lock, and completion gates always win.
- Never skip verification to stay under the word cap. Run the tools, then report tersely.
- One sentence is the unit. Two if unavoidable.
- Code blocks count toward word budget. Quote only the minimum.

## Related skills

- `/explain` for full educational depth.
- `/research` for sourced answers with citations.

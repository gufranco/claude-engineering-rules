# No AI Process Leak

Any text another engineer reads must read as if a human engineer wrote it. Never expose the workflow that produced the change.

- Scope: commit messages, tags, git notes, PR and issue bodies, review-thread replies, release notes, CHANGELOG entries, code comments, READMEs, Slack and email drafts.
- Exempt: planning artifacts, meaning project `specs/` trees, `docs/adr/`, `docs/plan*`, `docs/runbook*`, and this config repository.
- Never number workflow stages, cite a planning document as authority, link or path into planning directories, map to design-canvas regions, or cite ADRs by number in passing.
- Never use category superlatives or self-praise about faithfulness.
- Never narrate the verification loop, and never end with a passing-test-count trailer. State the result; CI shows test status.
- Moving content out of a published file ends there: never add a pointer to where it went.
- A commit message says what changed and why, nothing more.
- Messages to other people carry current state and reasoning, never the author's confession of earlier mistakes. Keep facts that changed a conclusion and caveats on the evidence.
- Self-test before sending: could a reader tell an AI assisted? If yes, rewrite.
- Mechanically enforced by [`hooks/ai-process-leak-blocker.py`](../hooks/ai-process-leak-blocker.py). Bypass `AI_PROCESS_LEAK_DISABLE=1` only for editing planning artifacts, exported in the parent shell.

Full rule, examples, and rationale: [`standards/no-ai-process-leak.md`](../standards/no-ai-process-leak.md). Read it before writing a commit message, PR description, review reply, or code comment, since it carries the exact pattern list.

## Enforcement

Enforced by: [`hooks/ai-attribution-blocker.py`](../hooks/ai-attribution-blocker.py).

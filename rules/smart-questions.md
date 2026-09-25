# Smart Questions

Question quality determines answer quality. Treat a request as a hypothesis to verify, and apply this format whenever asking, reporting, briefing a subagent, or closing a loop.

- Self-investigate first: rules, codebase grep, the named file, `git log`, open PRs, docs, memory
- XY framing: restate the underlying goal; when the literal ask solves a fragment, offer the goal-level path too
- Asking the user, in order: the specific question on the first line; what was investigated with paths; two or three options each explained in depth; a recommended option with its decisive reason, always
- One blocking question per turn; no "Can I ask?" or hello-only openers; no apologies or closers
- With `AskUserQuestion`, the recommended option comes first and its label ends with `(Recommended)`
- Reports lead with the symptom, then chronology, then hypothesis; short form `<object> - <deviation>`
- Bug reports: exact repro steps, error text verbatim, no pronouns, intermittent rate and pattern, freeze state before patching
- Subagent briefs carry scope, `file:line` refs, prior attempts, output shape, and a response length cap
- Close every task with one line tagged `FIXED:`, `RESOLVED:`, or `DONE:` naming what changed, where, and the verification
- Skip for trivial edits, approved plan steps, "just do it" lists, and plain yes or no

Full rule, examples, and rationale: [`standards/smart-questions.md`](../standards/smart-questions.md). Read it before putting a choice to the user or briefing a subagent.

## Enforcement

Enforced by: [`hooks/subagent-brief-quality.py`](../hooks/subagent-brief-quality.py).

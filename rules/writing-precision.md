# Writing Precision

Every piece of text passes a precision gate before it is finalized: chat replies, commits, PRs, reviews, docs, rules, and error messages.

- Every sentence earns its place; delete any whose removal loses nothing
- Lead with the action, reason second
- Concrete over abstract: name the API, not the quality; show the literal artifact, not a description of it
- One idea per sentence; one term per concept
- Right format: bullets for rules, numbered lists for steps, tables for lookups, Mermaid for flow
- Quantify; every stated decision carries its measurement and the limits of that evidence
- No weasel words: "should consider", "ideally", "where possible" become must or optional
- Every pronoun has an antecedent in the same or previous sentence; name the actor
- Tone: smart coworker on Slack, never servile, never clinical
- Parentheses only for `(default X)`, uppercase `(REQUIRED)`, `(e.g., ...)` once per paragraph, `(see X)` or `(per X)`
- Shareable text: no Markdown tables; offer to copy with Slack formatting
- Self-test: ambiguity, redundancy, format, example, obligation, substitution

Full rule, examples, and rationale: [`standards/writing-precision.md`](../standards/writing-precision.md). Read it before writing a rule, a standard, a PR description, or any document another person acts on.

## Enforcement

Enforced by: [`hooks/ai-slop-blocker.py`](../hooks/ai-slop-blocker.py).
Enforced by: [`hooks/banned-phrases-blocker.py`](../hooks/banned-phrases-blocker.py).
Enforced by: [`hooks/banned-prose-chars.py`](../hooks/banned-prose-chars.py).

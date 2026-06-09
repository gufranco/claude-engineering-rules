# Writing Precision

## Core Rule

Every piece of text you produce passes through a precision gate before being finalized. A one-line PR comment, a rule file, a commit message, a conversation reply: same gate.

## Precision Checklist

Before finalizing any text output:

### 1. Every sentence earns its place

If removing a sentence loses no information, remove it.

```
# Bad: two sentences saying the same thing
Use connection pooling for all database connections.
This ensures that connections are reused efficiently.

# Good: one sentence, same information
Use connection pooling for all database connections.
```

### 2. Lead with the action

State what to do first. Explain why second, only if the reason is non-obvious.

```
# Bad: reason first, action buried
Because individual connections per request exhaust the limit under load,
you should use connection pooling.

# Good: action first, reason second
Use connection pooling. Individual connections per request exhaust the
limit under load.
```

### 3. Concrete over abstract

Replace vague instructions with specific, verifiable constraints. If a rule can be interpreted two ways, it will be.

```
# Bad: vague, unverifiable
Write clean, maintainable code that follows best practices.

# Good: specific, verifiable
Functions under 30 lines. One export per file. No magic numbers.
```

```
# Bad: abstract
Handle errors appropriately.

# Good: concrete with categories
Every catch classifies the error: transient (retry with backoff),
permanent (fail immediately), or ambiguous (retry with limit, then fail).
```

### 4. One idea per sentence

If a sentence contains "and" connecting two unrelated ideas, split it.

```
# Bad: two ideas in one sentence
Validate inputs at the boundary and use structured logging for all services.

# Good: split
Validate inputs at the boundary. Use structured logging for all services.
```

### 5. Right format for the content

Each content type has a format that communicates it most precisely:

| Content type | Use |
|-------------|-----|
| Rules and constraints | Bullet points |
| Step-by-step procedures | Numbered lists |
| Comparisons and lookups | Tables |
| Behavior specification | Code examples |
| Conditional logic | Explicit if/then |
| Architecture and flow | Mermaid diagrams |

```
# Bad: paragraph where a table belongs
The create endpoint returns 201 on success, 400 for validation errors,
409 for duplicates, and 500 for server errors.

# Good: table
| Status | Meaning |
|--------|---------|
| 201 | Created successfully |
| 400 | Validation error |
| 409 | Duplicate resource |
| 500 | Server error |
```

### 6. Same term, same concept

Use one term for one concept throughout a document. Calling it "service" in one paragraph and "module" in the next creates false ambiguity.

```
# Bad: synonym rotation
The service validates the input. Then the module persists the entity.
The component sends a confirmation email.

# Good: consistent terminology
The service validates the input, persists the entity, and sends
a confirmation email.
```

### 7. Quantify when possible

Vague qualifiers are interpreted differently by every reader.

```
# Bad: vague
Keep functions small. Use short variable names when appropriate.

# Good: quantified
Functions under 30 lines. Variable names: 1-2 words for small scopes,
descriptive for public APIs.
```

### 8. Eliminate weasel words

"Should", "consider", "might want to", "ideally", "where possible" all leave an escape hatch. If the instruction is mandatory, say "must". If genuinely optional, say "optional" explicitly.

The full keyword vocabulary, the lowercase-primary convention, and the criteria for opt-in uppercase live in [`normative-keywords.md`](normative-keywords.md). The two rules compose: this rule strips escape hatches from sentences; the keyword rule picks the obligation word that goes in their place.

```
# Bad: weasel words
You should consider adding error handling where possible.
Tests should ideally cover edge cases.

# Good: explicit obligation
Add error handling at every system boundary.
Test edge cases: null inputs, empty strings, zero values, max lengths.
```

### 9. Pronoun discipline

Every pronoun must have an unambiguous antecedent in the same sentence or the immediately preceding one. The reader should not scan up multiple paragraphs to find what `it`, `this`, `they`, or `that` refers to. Covers `it`, `this`, `that`, `they`, `these`, `those`.

```
# Bad: ambiguous "it"
The schema is loaded and the validator runs. If it fails, retry.

# Good: name the subject
The schema is loaded and the validator runs. If the validator fails, retry.

# Bad: "this" with two candidate referents
Run the migration. The script then logs the result. This is irreversible.

# Good: name the referent
Run the migration. The script then logs the result. The migration is irreversible.
```

### 10. Active voice preference

Name the actor whenever the actor matters. Passive voice is acceptable only when the actor is unknown, irrelevant, or universally implied by context.

```
# Bad: passive hides the actor
The schema is validated before the write.

# Good: active names the actor
The handler validates the schema before the write.

# Acceptable passive: the actor is irrelevant or implied
The cache is invalidated every 24 hours.
The token must be signed with RS256.
```

Bullet-point rules in markdown often use a slightly different voice. "Run the linter before commit" is imperative, not passive, and is fine. The rule above targets sentences that obscure causality, not lists of commands.

### 11. Tone calibration

Default register: smart coworker on a team Slack. Direct enough to skip ceremony, warm enough to not feel transactional. Match the energy of the conversation: short question, short answer.

```
# YES, friendly-direct
Here's what I found.
Got it.
That doesn't look right.
Heads up, this might break X.
Correction: the file is at `src/index.ts`, not `src/main.ts`.
I don't know. Let me check.

# NO, too formal or servile
I shall now proceed to validate the schema.
Pursuant to your request, I have run the tests.
It would be my pleasure to clarify.
Permit me to clarify the next step.

# NO, too cold or clinical
REQUIREMENT: validate input.
Per rule 14.3.2, the migration must be idempotent.
Negative.
Acknowledged.
Confirmed.
```

Carve-out: a more formal register is acceptable in commit-message bodies, PR descriptions, code comments, and rule files where the surrounding voice is already formal. The conversational register applies to chat replies, tool-call descriptions, status updates, error reports, and review replies.

A useful self-check: read the draft aloud. If it sounds like a teammate, ship it. If it sounds like a customer-service script or a military report, rewrite.

### 12. Parentheses carve-outs

The "no parens in prose" rule from [`CLAUDE.md`](../CLAUDE.md) Writing Style stays in force for thought-interruption asides, definition repetition, and long parentheticals. Four specific patterns are carved out because they serve real technical communication.

Allowed:

| Pattern | Example | Why allowed |
|---------|---------|-------------|
| `(default X)` or `(default: X)` after a parameter mention | `GAN_EVAL_MODE` (default `playwright`) | The paren is part of the parameter's signature, not a thought interruption |
| `(REQUIRED)`, `(OPTIONAL)`, `(RECOMMENDED)` uppercase emphasis labels | The full URL (REQUIRED) must include the scheme | Typographic emphasis, not a parenthetical clause. Uppercase only; lowercase `(required)` falls under the BCP 14 keyword reading and stays banned |
| `(e.g., X)` and `(i.e., X)` once per paragraph | Validate at boundaries (e.g., HTTP handlers and queue consumers) | A scoped, well-known shorthand for clarification |
| `(see X)` and `(per X)` cross-references | Use Zod (see [`code-style.md`](code-style.md)) | Compact alternative to "see X" as a separate sentence |

Still forbidden:

| Pattern | Example | Why still forbidden |
|---------|---------|---------------------|
| Mid-sentence aside | "The handler (which also runs on websockets) validates the input" | Real thought interruption; restructure |
| Definition repetition | "the cache (the Redis store)" | Use a comma or a separate sentence |
| Long parenthetical | Parens spanning more than 80 characters of inner text | Hide the main clause |

The audit script [`.github/scripts/audit-writing-quality.py`](../.github/scripts/audit-writing-quality.py) skips the four allowed patterns and flags the rest. Authors apply judgment on lines the audit cannot mechanically classify.

## Shareable Text

Text the user will copy into Slack, email, or other tools must survive the paste without losing structure.

- Use flat prose, bold labels, and bullet lists. Never use Markdown tables in shareable text. Tables render as broken plaintext outside Markdown-aware contexts.
- Tables are fine in terminal output, code review findings, README files, and rule files where Markdown renders natively.
- After generating any text the user might share, ask: "Want me to copy this to your clipboard with Slack formatting?"
- When copying for Slack: replace `**bold**` with `*bold*`, keep backtick code spans, use `pbcopy` on macOS.

## Self-Test Gate

After writing any text, read it back and verify:

1. **Ambiguity test.** Could a developer follow this text and arrive at a wrong interpretation? If yes, add the constraint or example that blocks the wrong path.
2. **Redundancy test.** Does any sentence restate something already said? Remove the duplicate.
3. **Format test.** Is there a paragraph that should be a list or table? Convert it.
4. **Example test.** Is there an instruction where the meaning could vary across readers? Add the example that anchors it. Examples are non-negotiable for rules, standards, and any instructional text.
5. **Obligation test.** Does every "should" actually mean "must"? If yes, say "must". If optional, say "optional".

For question messages, status updates, error reports, subagent prompts, and loop-closure lines, apply [`rules/smart-questions.md`](smart-questions.md) in addition to this gate.

## Scope

This rule governs all text output without exception:

- Conversation replies
- PR titles and descriptions
- Review comments, both inline and summary
- Commit messages
- Documentation and README updates
- Rule and standard files
- Code comments
- Error messages in code
- Skill and prompt files

## Enforcement

Enforced by: [`hooks/banned-phrases-blocker.py`](../hooks/banned-phrases-blocker.py).
Enforced by: [`hooks/banned-prose-chars.py`](../hooks/banned-prose-chars.py).

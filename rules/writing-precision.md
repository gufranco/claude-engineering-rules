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

```
# Bad: weasel words
You should consider adding error handling where possible.
Tests should ideally cover edge cases.

# Good: explicit obligation
Add error handling at every system boundary.
Test edge cases: null inputs, empty strings, zero values, max lengths.
```

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

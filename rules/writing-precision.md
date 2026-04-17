# Writing Precision

## Core Rule

Every piece of text you produce passes through a precision gate before being finalized. A one-line PR comment, a rule file, a commit message, a conversation reply: same gate.

## Precision Checklist

### 1. Every sentence earns its place

If removing a sentence loses no information, remove it.

### 2. Lead with the action

State what to do first. Explain why second, only if the reason is non-obvious.

```
# Good
Use connection pooling. Individual connections per request exhaust the limit under load.
```

### 3. Concrete over abstract

Replace vague instructions with specific, verifiable constraints.

```
# Good
Functions under 30 lines. One export per file. No magic numbers.

# Good
Every catch classifies the error: transient (retry with backoff),
permanent (fail immediately), or ambiguous (retry with limit, then fail).
```

### 4. One idea per sentence

If a sentence contains "and" connecting two unrelated ideas, split it.

### 5. Right format for the content

| Content type | Use |
|-------------|-----|
| Rules and constraints | Bullet points |
| Step-by-step procedures | Numbered lists |
| Comparisons and lookups | Tables |
| Behavior specification | Code examples |
| Conditional logic | Explicit if/then |
| Architecture and flow | Mermaid diagrams |

### 6. Same term, same concept

Use one term for one concept throughout a document. Do not rotate synonyms.

### 7. Quantify when possible

```
# Good
Functions under 30 lines. Variable names: 1-2 words for small scopes,
descriptive for public APIs.
```

### 8. Eliminate weasel words

"Should", "consider", "might want to", "ideally", "where possible" all leave an escape hatch. If the instruction is mandatory, say "must". If genuinely optional, say "optional" explicitly.

```
# Good
Add error handling at every system boundary.
Test edge cases: null inputs, empty strings, zero values, max lengths.
```

## Shareable Text

Text the user will copy into Slack or email must survive the paste without losing structure.

- Use flat prose, bold labels, and bullet lists. Never use Markdown tables in shareable text
- Tables are fine in terminal output, code review findings, README files, and rule files
- When copying for Slack: replace `**bold**` with `*bold*`, keep backtick code spans, use `pbcopy` on macOS

## Self-Test Gate

After writing any text, verify:

1. **Ambiguity test.** Could a developer follow this and arrive at a wrong interpretation? If yes, add the constraint or example that blocks the wrong path
2. **Redundancy test.** Does any sentence restate something already said? Remove the duplicate
3. **Format test.** Is there a paragraph that should be a list or table? Convert it
4. **Example test.** Is there an instruction where meaning could vary across readers? Add the example that anchors it. Examples are non-negotiable for rules, standards, and instructional text
5. **Obligation test.** Does every "should" actually mean "must"? If yes, say "must"

## Scope

This rule governs all text output: conversation replies, PR titles and descriptions, review comments, commit messages, documentation and README updates, rule and standard files, code comments, error messages in code, and skill and prompt files.

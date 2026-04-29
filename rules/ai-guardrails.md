# AI Guardrails

## Core Principle

Treat all AI-generated code as junior developer output. It compiles, it looks plausible, it often has subtle design flaws. 62% of AI-generated code contains design issues that pass syntax checks but fail under real-world conditions. Never trust, always verify.

## Plan Before Generating

Never generate code without a plan. The cost of planning is near zero. The cost of refactoring wrong-direction code is high.

1. State the approach in plain language.
2. Identify the files that will change.
3. Verify interfaces, types, and dependencies before writing.
4. Break the work into chunks small enough to review in isolation.

## Small Chunks, Always

Generate code in small, reviewable units. A 500-line generation is unreviable. A 50-line generation is verifiable.

| Chunk size | Reviewability | Risk |
|-----------|--------------|------|
| Under 50 lines | High | Low |
| 50-150 lines | Moderate | Moderate |
| Over 150 lines | Low | High, split required |

## Review Every Generation

Before committing any AI-generated code, verify:

| Check | What to look for |
|-------|-----------------|
| Logic correctness | Does the code do what was asked, not just something that looks similar? |
| Edge cases | Are nulls, empty arrays, zero values, and boundary conditions handled? |
| Error paths | Does every catch classify and handle the error, or just log and continue? |
| Type safety | Are there any `any` types, unsafe casts, or missing null checks? |
| Dead code | Did the generation include unused imports, unreachable branches, or vestigial logic? |
| Naming | Do names match the domain language used in the rest of the codebase? |
| Duplication | Does the generated code duplicate logic that already exists elsewhere? |
| Over-engineering | If 200 lines could be 50, rewrite. Would a senior engineer call this overcomplicated? |
| Surgical scope | Every changed line traces to the request. No adjacent "improvements". See `rules/surgical-edits.md` |

## Never Commit Code You Cannot Explain

If you cannot explain what a generated block does line by line, do not commit it. Read it, trace the logic, verify the data flow. "It works" is not understanding. Understanding means you can predict what happens with unexpected input.

## Multi-Agent Validation

When agents generate code, the orchestrator must review the output with the same rigor as any other code change. Agent output is not pre-validated. Run the full self-review loop from the completion gates.

## AI-Specific Defect Patterns

Track these patterns. They recur across AI-generated code.

| Pattern | Description |
|---------|------------|
| Plausible hallucination | Function calls, imports, or API methods that look correct but do not exist |
| Optimistic error handling | Catches that log but do not propagate, recover, or classify |
| Shallow validation | Checks types but not business rules, ranges, or invariants |
| Copy-paste drift | Repeated blocks with minor variations instead of a single parameterized function |
| Missing cleanup | Resources opened but never closed, listeners added but never removed |
| Invented APIs | Method signatures that seem right for the library but do not match the actual API |

## Quality Metrics

When AI-generated code causes a defect in review or production, record:

- What the defect was
- Which AI-specific pattern it matched
- Whether the self-review loop would have caught it
- What check was missing or skipped

Use these records to tighten the review process over time.

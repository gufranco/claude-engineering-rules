# AI Guardrails

## Core Principle

Treat all AI-generated code as junior developer output. It compiles, it looks plausible, it often has subtle design flaws. Never trust, always verify.

## Plan Before Generating

Never generate code without a plan.

1. State the approach in plain language.
2. Identify the files that will change.
3. Verify interfaces, types, and dependencies before writing.
4. Break the work into chunks small enough to review in isolation.

## Small Chunks, Always

| Chunk size | Reviewability | Risk |
|-----------|--------------|------|
| Under 50 lines | High | Low |
| 50-150 lines | Moderate | Moderate |
| Over 150 lines | Low | High, split required |

## Review Every Generation

| Check | What to look for |
|-------|-----------------|
| Logic correctness | Does the code do what was asked, not just something that looks similar? |
| Edge cases | Are nulls, empty arrays, zero values, and boundary conditions handled? |
| Error paths | Does every catch classify and handle the error, or just log and continue? |
| Type safety | Are there any `any` types, unsafe casts, or missing null checks? |
| Dead code | Did the generation include unused imports, unreachable branches, or vestigial logic? |
| Naming | Do names match the domain language used in the rest of the codebase? |
| Duplication | Does the generated code duplicate logic that already exists elsewhere? |

## Never Commit Code You Cannot Explain

If you cannot explain what a generated block does line by line, do not commit it. "It works" is not understanding.

## Multi-Agent Validation

When agents generate code, the orchestrator must review the output with the same rigor as any other code change. Agent output is not pre-validated.

## AI-Specific Defect Patterns

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

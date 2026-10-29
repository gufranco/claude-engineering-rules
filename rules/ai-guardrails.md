# AI Guardrails

Treat all AI-generated code as junior developer output: never trust, always verify.

- Plan before generating: state the approach, list the files, verify interfaces, split into chunks.
- Target chunks under 50 lines; anything over 150 lines must be split.
- Review every generation for logic, edge cases, error paths, type safety, dead code, naming, duplication, over-engineering, and surgical scope.
- Never commit code you cannot explain line by line.
- Agent output gets the same full self-review as any other change.
- Watch for hallucinated APIs, optimistic error handling, shallow validation, copy-paste drift, and missing cleanup.
- When AI code causes a defect, record the defect, the matched pattern, and the missed check.

Full rule, examples, and rationale: [`standards/ai-guardrails.md`](../standards/ai-guardrails.md). Read it before reviewing a large generation or agent output.

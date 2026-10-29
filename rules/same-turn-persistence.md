# Same-Turn Persistence

A correction produces a file write before the turn that received it ends, or it did not happen. Acknowledgment alone is never persistence.

- The response acknowledging a correction contains the Write or Edit that persists it; never defer to later, the end of the task, or a retrospective.
- A self-caught mistake carries the same obligation.
- Write the root-cause behavior pattern, never the surface symptom.
- Route: working behavior to a `feedback` memory or the rule it sharpens; user facts to `user`; ongoing work to `project` or the vault when one is configured; repo gotchas to that repo's instruction file; a repeatedly violated rule to a hook.
- Update an existing file that fits; never create a near-duplicate.
- Admission bar: would a future session get stuck or do something wrong without this? If no, skip it and say what was skipped and why.
- Reject: already in a rule, derivable from code in a turn or two, one-offs, standard tool behavior, restatements.
- Accept: costly gotchas with no trace in code, preferences contradicting a default, wrong answers that look correct, constraints invisible at the call site.
- Write each accepted item as one dense line.

Full rule, examples, and rationale: [`standards/same-turn-persistence.md`](../standards/same-turn-persistence.md). Read it before deciding where a correction goes or whether it clears the bar.

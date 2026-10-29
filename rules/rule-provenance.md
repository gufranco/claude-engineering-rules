# Rule Provenance

A rule's history lives in the work record, never in the artifact. The repository states only the current rule; when it became binding, why, and how often its failure recurred live in the private knowledge vault.

- Rules, standards, skills, agents, hooks, tests, and READMEs describe the current state: what holds, how to apply it, and what enforces it. No dates of changes, no "added", "amended" or "promoted" lines, no quotes of instructions, no session, pull request, ticket, repository, employer, or person behind a change.
- Record the date, recurrence count, and concrete failure of each new or changed rule in the vault, when `SECOND_BRAIN_VAULT` is set; workspace prompts and plans may also carry it.
- Log a lesson on first sight; promote it to a rule on the third occurrence. Skip the threshold only for irreversible, silent, security-crossing, or unbounded failures.
- State the failure mechanism inline when it explains the rule, written generically: name the mechanism, never the project or the person where it happened.
- A new rule ships as a short core in [`rules/`](.) plus its full text in [`standards/`](../standards/); CI fails the always-loaded set above 120,000 characters.
- Prune rules whose origin no longer applies or is now caught mechanically, merge rules sharing an origin, and record each removal in the vault.

Full rule and rationale: [`standards/rule-provenance.md`](../standards/rule-provenance.md). Read it before adding, promoting, or deleting a rule.

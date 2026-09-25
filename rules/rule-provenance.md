# Rule Provenance

Every rule states when it became binding and what made it binding.

- A rule file carries a `Provenance` section: ISO date, recurrence count or `single-incident`, and the concrete failure mechanism.
- Log a lesson on first sight; promote it to a rule on the third occurrence.
- Skip the threshold only for irreversible, silent, security-crossing, or unbounded failures, naming the condition.
- State the incident inline with the rule when known.
- Prune rules whose origin no longer applies or is now caught mechanically, merge rules sharing an origin, and record every removal.

Full rule and rationale: [`standards/rule-provenance.md`](../standards/rule-provenance.md). Read it before adding, promoting, or deleting a rule.

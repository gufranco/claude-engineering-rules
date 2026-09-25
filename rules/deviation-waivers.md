# Deviation Waivers

Deviating from a rule is allowed. Deviating silently is not: surface the tradeoff, get human approval, and record it where reviewers read it.

- A waiver goes in the PR body, or the change's plan folder when there is no PR, with seven required fields: `rule`, `scope`, `approved_by`, `rationale`, `alternatives`, `risk`, `revisit`.
- Scope is one file, function, or change; never a directory, language, or category.
- A waiver you approved yourself is a silent deviation.
- Never waivable: security or privacy boundaries, legal or compliance obligations, silent data loss or corruption, verification gates, truthfulness to a reader.
- A bypass means the check is wrong about this input; a waiver means the rule is right and this case is the exception. Never bypass a correct check.
- A tripwire halts work at a stated threshold and proceeds only on a recorded waiver.

Full rule, examples, and rationale: [`standards/deviation-waivers.md`](../standards/deviation-waivers.md). Read it before writing a waiver or reaching for a bypass.

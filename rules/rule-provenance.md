# Rule Provenance

## Core Rule

Every rule states when it became binding and what made it binding. A rule with no traceable origin cannot be judged, cannot be pruned, and cannot be told apart from a guess that happened to get written down.

Two things follow. A new rule carries a provenance stamp. And a lesson does not become a rule on first sight: it is logged, and it earns rule status by recurring.

## Why This Rule Exists

A rule set grows monotonically unless something opposes it. Nothing here opposed it. The result is a large body of rules where a reader cannot distinguish three categories that demand completely different treatment:

| Category | What it deserves |
|---|---|
| Written after a real failure, with the failure still reproducible | Keep, and never relax without understanding the failure |
| Written after a real failure whose cause has since been removed | Delete; the constraint outlived its reason |
| Written speculatively because it sounded correct | Test against reality before trusting it |

Without provenance, all three read identically, so pruning is impossible and every rule is defended with equal force. Provenance is what makes a rule set shrinkable.

## The Provenance Stamp

Every rule file carries a `Provenance` section, and every rule added to an existing file carries a one-line stamp.

```markdown
## Provenance

Promoted 2026-08-26 after the third recurrence. Origin: a scripted check read
`stderr` through `2>/dev/null`, so the loop over its output ran zero times and
reported success. Recurred in a lint helper and a CI gate before promotion.
```

Three fields, all required:

| Field | Content |
|---|---|
| Date | When the rule became binding, ISO 8601 |
| Recurrence | How many times the underlying failure was observed before promotion, or `single-incident` when the blast radius justified skipping the threshold |
| Origin | The concrete failure, in one or two sentences, specific enough that a reader can decide whether it still applies |

An origin naming a mechanism outranks an origin naming a feeling. "Reads plausible but silently scans the whole table" is an origin. "Seemed risky" is not.

## The Promotion Threshold

A lesson is logged on first occurrence and promoted on the third. Between those points it lives as a memory entry per [`same-turn-persistence.md`](same-turn-persistence.md), where it is cheap and easily deleted.

Three occurrences, because:

- **One** is an incident. It may be specific to that file, that library version, or that afternoon.
- **Two** is a coincidence worth watching. Promoting here produces rules tuned to a pair of cases that shared an accident.
- **Three** is a pattern. The failure has now survived different contexts, which is the only evidence that a general rule will fire correctly.

### Skipping the threshold

Promote on the first occurrence when the failure is irreversible, silent, or catastrophic:

| Condition | Example |
|---|---|
| Data loss or corruption | A migration renamed after being applied, so it re-runs against production |
| A security or privacy boundary crossed | A credential read into a transcript |
| Fails without an error signal | A version mismatch that renders wrong output instead of raising |
| Damage is unbounded or unrecoverable | A destructive command run against the wrong environment |

Stamp these `single-incident` and name the condition that justified skipping. Skipping is the exception, and a rule set where most rules are `single-incident` has stopped applying the threshold.

## Rules Carry Their Incident

The strongest form of a rule states the failure that produced it, inline, where the rule is read.

```markdown
Never rename a migration that has already been applied. The filename is its key
in the migrations table, so a rename re-runs it against production.

Never write a non-primitive into the shared config document. Client startup
iterates every top-level field and throws unguarded on a type it cannot store,
so the client fails to launch for every user. Caused a production outage and a
revert. The constraint is permanent, since a deployed client cannot be fixed
retroactively.
```

Both examples do three things a bare prohibition does not: they name the mechanism, so a reader can recognize a novel variant; they say whether the constraint is permanent or contingent; and they make the rule unarguable, because arguing requires disputing the incident rather than the author's taste.

A rule with no incident behind it is not forbidden. It is simply visible as speculative, which is the point.

## Pruning

A rule set that only grows is a rule set nobody finishes reading. Provenance makes removal decidable.

Review triggers:

- The origin names a tool, version, platform, or workflow the project no longer uses.
- The origin names a defect class now caught mechanically by a hook, a linter, or a type checker. The rule becomes a pointer to the mechanism, or it goes.
- The rule has never fired in observed work and its origin was speculative.
- Two rules share an origin. They are one rule.

Deleting a rule is itself a change with provenance: record what was removed and which condition retired it. A rule that comes back is evidence the removal was wrong, and that evidence is only readable if the removal was recorded.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| A new rule with no date and no origin | Cannot be judged, cannot be pruned, indistinguishable from a guess |
| Promoting a lesson on first sight without a skip condition | Produces rules tuned to one accident |
| An origin that describes a feeling rather than a mechanism | A reader cannot tell whether a new case is the same case |
| Writing a prohibition when the incident is known but omitting it | Turns an unarguable rule into a matter of taste |
| Marking a rule `single-incident` without naming the qualifying condition | The threshold stops meaning anything |
| Deleting a rule with no record of why | The next recurrence looks like a new discovery |
| Two rules with the same origin in different files | Guaranteed to drift apart |

## Interaction With Other Rules

[`same-turn-persistence.md`](same-turn-persistence.md) is the intake path. A lesson lands there first, and its recurrence count is what feeds this rule.

[`writing-precision.md`](writing-precision.md) section 7b already requires that a stated decision carry the measurement behind it. This rule applies the same obligation to the rules themselves.

[`normative-keywords.md`](normative-keywords.md) governs the obligation word. Provenance governs whether the obligation should exist at all.

[`doc-truth.md`](doc-truth.md) governs a document going out of sync with code. Provenance governs a rule going out of sync with the reason it was written.

## Provenance

Promoted 2026-08-26, `single-incident`, under the unbounded-growth condition: a rule set had reached a size where speculative and incident-backed rules were indistinguishable, which makes pruning impossible and defends every rule with equal force. Origin: an audit of an unrelated multi-repository rule set whose binding rules each carried a promotion date and a recurrence count, and were therefore prunable.

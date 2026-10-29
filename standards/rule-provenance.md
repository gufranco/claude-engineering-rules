# Rule Provenance

## Core Rule

A rule's history belongs to the work record, and the artifact states only the current rule. The repository is the artifact: it says what holds, how to apply it, and what enforces it. When a rule became binding, how often its failure recurred, and what incident or instruction produced it are kept in the private knowledge vault, where they stay useful for pruning without being published.

A lesson still does not become a rule on first sight: it is logged, and it earns rule status by recurring.

## Why History Stays Out of the Artifact

The repository is public. A change log written into a rule publishes who asked for what, when, in which project, and for which employer. None of that helps a reader apply the rule, and all of it is private.

History is still needed. Without it, three kinds of rule read identically:

| Category | What it deserves |
|---|---|
| Written after a real failure, with the failure still reproducible | Keep, and never relax without understanding the failure |
| Written after a real failure whose cause has since been removed | Delete; the constraint outlived its reason |
| Written speculatively because it sounded correct | Test against reality before trusting it |

So the record is kept, in the vault, and consulted before a rule is pruned, promoted, or relaxed.

## What the Artifact Carries

| Carries | Never carries |
|---|---|
| The rule, stated in the present tense | Dates of additions, amendments, or promotions |
| How to apply it, with generic examples | Quotes of the instruction that produced it |
| The failure mechanism, when it explains the rule | The project, repository, pull request, ticket, session, employer, or person where the failure happened |
| What enforces it: the hook, lint rule, or CI job | Recurrence counts and `single-incident` stamps |
| | Wording such as "previously", "used to", "now" that narrates a change |

A mechanism is written generically. "A rename re-runs an applied migration, because the filename is its key in the migrations table" explains the rule. "Broke production in project X on a given date" is history.

## The Work Record

Each new or changed rule gets a record in the vault, when `SECOND_BRAIN_VAULT` is set:

| Field | Content |
|---|---|
| Date | When the rule became binding or changed, ISO 8601 |
| Recurrence | How many times the failure was observed before promotion, or `single-incident` with the condition that justified skipping the threshold |
| Origin | The concrete failure or instruction, specific enough to decide whether it still applies |

Workspace prompts and plan folders may carry the same history while the work is in progress. Neither is committed.

## The Promotion Threshold

A lesson is logged on first occurrence and promoted on the third. Between those points it lives as a vault note or memory entry per [`same-turn-persistence.md`](../rules/same-turn-persistence.md), where it is cheap and easily deleted.

- **One** is an incident. It may be specific to that file, that library version, or that afternoon.
- **Two** is a coincidence worth watching.
- **Three** is a pattern. The failure has survived different contexts, which is the evidence that a general rule will fire correctly.

### Skipping the threshold

Promote on the first occurrence when the failure is irreversible, silent, or catastrophic:

| Condition | Example |
|---|---|
| Data loss or corruption | A migration renamed after being applied, so it re-runs against production |
| A security or privacy boundary crossed | A credential read into a transcript |
| Fails without an error signal | A version mismatch that renders wrong output instead of raising |
| Damage is unbounded or unrecoverable | A destructive command run against the wrong environment |

Record the skip condition in the vault entry.

## Rules Carry Their Mechanism

The strongest form of a rule states the mechanism that makes it necessary, inline, where the rule is read:

```markdown
Never rename a migration that has already been applied. The filename is its key
in the migrations table, so a rename re-runs it against production.
```

The mechanism lets a reader recognize a novel variant and makes the rule unarguable. It is part of the current rule, not its history, so it belongs in the artifact.

## Pruning

Review triggers:

- The origin names a tool, version, platform, or workflow no longer used.
- The origin names a defect class now caught mechanically by a hook, a linter, or a type checker. The rule becomes a pointer to the mechanism, or it goes.
- The rule has never fired in observed work and its origin was speculative.
- Two rules share an origin. They are one rule.

Each removal is recorded in the vault: what was removed and which condition retired it.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| A `Provenance` section, or a dated "added" or "amended" line, in a repository file | Publishes the work history; the vault holds it |
| Quoting the instruction that produced a rule | Publishes a private conversation |
| Naming the project, employer, repository, pull request, or person behind a rule | Publishes private context |
| A new rule with no vault record | Cannot be judged or pruned later |
| Promoting a lesson on first sight without a skip condition | Produces rules tuned to one accident |
| Two rules with the same origin in different files | Guaranteed to drift apart |

## Enforcement

[`.github/scripts/validate-public-content.py`](../.github/scripts/validate-public-content.py) runs in CI and in `make validate`. It fails a tracked file that carries a `Provenance` heading, a dated change line, an attribution phrase such as `by direct user instruction`, or a cross-repository pull request reference. [`hooks/private-terms-guard.py`](../hooks/private-terms-guard.py) blocks a write or commit in this repository that names a term from the private denylist kept in the vault.

## Interaction With Other Rules

[`same-turn-persistence.md`](../rules/same-turn-persistence.md) is the intake path. A lesson lands there first, and its recurrence count is what feeds this rule.

[`doc-truth.md`](../rules/doc-truth.md) governs a document going out of sync with code. This rule governs a rule going out of sync with the reason it was written.

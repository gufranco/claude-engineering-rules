# Deviation Waivers

## Core Rule

Deviating from a rule is allowed. Deviating **silently** is not.

A deviation is legitimate when the tradeoff was surfaced to the person running the session, they approved it, and the approval was recorded where a reviewer will find it. A silent deviation is a violation regardless of how good the reasoning was, because the reasoning left no trace.

The framing matters: a surfaced and approved deviation is the system working, not the system failing.

## Why This Rule Exists

A rule set with no legitimate exception path does not produce compliance. It produces two worse outcomes.

The first is the escape hatch used as a substitute for a conversation. When the only way past a rule is a bypass environment variable, a genuine design disagreement gets resolved by silencing the check. Nothing is recorded, no one reviews it, and the next session sees a clean run.

The second is a rule quietly ignored because following it would produce a worse result, with the diff shipped as though the rule had been met.

Both are failures of the same missing thing: a way to say "not here, and here is why" that costs less than lying and more than nothing.

## The Waiver Record

A waiver is a structured block placed where the change is reviewed, in the pull request body, or in the change's plan folder when there is no pull request. Seven fields, all required.

```markdown
### Waiver

- rule: code-style / file size under 500 lines
- scope: packages/engine/src/scheduler.ts, this file only
- approved_by: <the person who approved, and when>
- rationale: the state machine's transition table is one unit; every split
  attempted so far moved a case away from the guard that validates it
- alternatives: extracting the guards into a sibling module, rejected because
  the guard and the case must change together and a split invites drift
- risk: the file keeps growing as states are added; the next state pushes it
  past the point where the transition table stops fitting on a screen
- revisit: when the state count exceeds twelve, or at the next refactor of
  this module
```

| Field | Why it is required |
|---|---|
| `rule` | Names exactly what is being waived. "Some style rule" is not a waiver |
| `scope` | Bounds the waiver to a file, a function, or a change. Never a directory, a language, or a category |
| `approved_by` | Records that a human agreed. A waiver you granted yourself is a silent deviation with extra formatting |
| `rationale` | The tradeoff, in the concrete case. Not a restatement of the rule's cost in general |
| `alternatives` | What was tried or considered and why it lost. A waiver with no alternatives considered was not a decision |
| `risk` | What goes wrong if the waiver turns out to be a mistake. Names it before it happens |
| `revisit` | The condition that reopens it. A waiver with no exit is a permanent rule change made by one person in one afternoon |

## Tripwires

Some rules are better expressed as a threshold that stops the work than as a boundary that fails it. A tripwire is not a correctness line. It is the point where the shape of the design must be discussed before more of it is built.

```markdown
A change that would add more than N of <thing> stops before writing any of it,
presents the shape tradeoff, and proceeds only on approval recorded as a waiver.
```

The distinction from a hard rule is the response. Crossing a hard rule means the code is wrong. Crossing a tripwire means the code may be fine and the approach needs a second opinion first, while backing out is still cheap.

A tripwire is worth setting where the cost of a wrong shape scales with how much of it gets built: a proliferating set of near-identical definitions, a growing number of parallel branches, an expanding public surface. State the number, state what stops, and state what gets presented.

## What Cannot Be Waived

A waiver moves a judgment from the model to a person. It does not move a boundary that is not the person's to move in a pull request body.

| Not waivable | Why |
|---|---|
| A security or privacy boundary | The affected party is not in the conversation |
| A legal or compliance obligation | Approval requires authority nobody in the session has |
| Anything that silently loses or corrupts data | The failure is invisible and irreversible |
| A verification gate | A waived gate is an unverified claim; see [`found-fix.md`](found-fix.md) |
| Truthfulness of a claim to a reader | There is no version of this that is the system working |

For these, the answer is to change the design, or to stop and escalate. Not to record a waiver.

## Relationship To Bypasses

A mechanical bypass and a waiver answer different questions.

| | Bypass | Waiver |
|---|---|---|
| Answers | "The check is wrong about this input" | "The rule is right, and this case is the exception" |
| Blast radius | Everything the check would have caught in that window | Exactly the named scope |
| Record | A log entry nobody reads | A reviewed block in the change |
| Reviewed by | Nobody | The approver, then every reviewer |

The bypass discipline in [`../CLAUDE.md`](../CLAUDE.md) stands unchanged: once per session per hook, for a named false positive, never as a standing setting. This rule covers the case that discipline was being stretched to cover. When the check is right and the case is still an exception, the answer is a waiver and a passing run, never a bypass and a silenced one.

Naming the false positive out loud is still the test. If that sentence cannot be written honestly, the check is right, and what is needed is a waiver.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| Deviating from a rule without surfacing it | The definition of a silent deviation |
| A waiver you approved yourself | Approval by the party who wants the exception is not approval |
| A waiver scoped to a directory, a language, or a category | Waivers bound a case; anything broader is a rule change in disguise |
| A waiver with no `revisit` condition | A permanent rule change made unilaterally |
| A waiver with no alternatives considered | Records a preference, not a decision |
| Using a bypass where the check is correct | Converts a design conversation into a silenced run |
| Waiving a verification gate | An unverified change reported as verified |
| A rationale restating the rule's general cost rather than this case | Applies to every case, so it justifies nothing |

## Interaction With Other Rules

[`../CLAUDE.md`](../CLAUDE.md) "Rule Priority" and "Hook Bypass Discipline" are unchanged. This rule adds the path that was missing between full compliance and a silenced check.

[`rule-provenance.md`](rule-provenance.md) closes the loop. Waivers accumulating against the same rule for the same reason are evidence the rule is mis-scoped, and that is a pruning or rewriting trigger, not a reason to keep granting waivers.

[`surgical-edits.md`](surgical-edits.md) is unaffected. A waiver widens what is permitted at one point, never what may be changed.

[`no-ai-process-leak.md`](no-ai-process-leak.md) governs the wording. A waiver in a pull request body is written as an engineering note, not as a compliance artifact.

## Provenance

Promoted 2026-08-26, `single-incident`, under the unbounded-growth condition applied to bypasses rather than rules: an absolute rule set whose only exception path was a mechanical bypass pushes genuine design disagreements into silenced checks, which leaves no record. Origin: an audit of an external modeling standard whose binding requirement was the process rather than the defaults, stating that a silent deviation is a violation and a surfaced-and-approved one is the system working, with approvals recorded as structured waivers carrying rule, owner, approver, rationale, alternatives, and a revisit condition.

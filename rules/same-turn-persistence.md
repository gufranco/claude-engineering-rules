# Same-Turn Persistence

## Core Rule

A correction produces a file write before the turn that received it ends, or it did not happen.

"Noted", "good point", "I will do better", and "I will keep that in mind" are not persistence. They are promises that evaporate when the session closes. The next session starts from the same file set as this one, so the file set is the only thing that carries a correction forward.

This rule binds the moment feedback arrives. It does not wait for a retrospective, a checkpoint, or the end of a task.

## Why This Rule Exists

[`/retro`](../skills/retro/SKILL.md) already extracts corrections into durable config, and it works. Its weakness is timing: it is post-hoc and opt-in, so a correction given early in a long session survives only if someone remembers to run the skill much later. Everything between the correction and the retrospective is a window where the same mistake can recur and where the reasoning behind the correction decays into a one-line summary.

The fix is not a better retrospective. It is moving the write to the moment the correction is understood, while the root cause is still visible.

## The Four Obligations

### 1. Write in the same turn

The response that acknowledges a correction contains the `Write` or `Edit` that persists it. Not the next response, not "at the end of this task", not "when we run `/retro`".

When the correction arrives mid-task and stopping would lose more than it saves, the write still lands in that same response, before the task resumes. A one-line addition to an existing file is cheap; re-learning the correction next month is not.

### 2. A self-caught mistake gets the same treatment

Do not wait to be told. Noticing your own rule violation, wrong default, or wasted approach carries the identical obligation as being corrected by the user. The goal is zero repeats across sessions, and most repeats are of mistakes nobody bothered to mention.

### 3. Target the root cause, not the symptom

The write describes the behavior pattern that produced the mistake, not the surface event.

| Symptom, do not write this | Root cause, write this |
|---|---|
| "I forgot to call the search tool" | "I default to answering from memory when the question sounds familiar" |
| "I used the wrong flag" | "I inferred flag semantics from the operating system instead of resolving the implementation" |
| "I ran the tests too late" | "I treat verification as a closing step rather than as the thing that decides whether the work is done" |
| "I wrote a comment in a test" | "I treat test files as exempt from rules that govern production code" |

A symptom-level note fires only on an exact repeat. A root-cause note fires on the whole class.

### 4. Route the write to the right surface

| What the correction is about | Where it goes |
|---|---|
| How you should work, generally | A `feedback` memory, or an existing rule in [`rules/`](.) when the correction sharpens one |
| A fact about the user | A `user` memory |
| A fact about ongoing work | A `project` memory, or the vault per [`knowledge-notes.md`](knowledge-notes.md) |
| A gotcha in a specific repository | That repository's own instruction file |
| A rule that keeps being violated | A hook, per [`/hookify`](../skills/retro/SKILL.md) |

A correction that fits an existing file updates that file. It does not create a second file saying almost the same thing. See [`memory-supersede.md`](memory-supersede.md).

## The Admission Bar

Mandatory persistence without an admission bar inflates the config until every session pays for lines nobody needed. The two rules are a pair; adopting one without the other makes things worse.

Before writing, answer one question: **would a future session actually get stuck, or do something wrong, without this?**

If the answer is no, do not write it. Say what you would have written and why it did not clear the bar, so the judgment is visible rather than silent.

Reject:

- Anything already stated in an existing rule, standard, or checklist item.
- Anything derivable from reading the code in a turn or two.
- A one-off that has no plausible second occurrence.
- Standard behavior of a well-known framework or tool.
- A restatement of a correction already persisted, in different words.

Accept:

- A gotcha that cost real turns to discover and leaves no trace in the code.
- A user preference that contradicts a reasonable default.
- A failure mode where the wrong answer looks correct.
- A constraint whose reason is invisible at the call site.

Every accepted line is paid for in every future session. Write it as one dense line, not a paragraph.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| Acknowledging a correction with no file write in the same response | The correction survives only as long as the session does |
| "I will add this to memory later" | Later does not arrive; the session ends first |
| Deferring the write to a retrospective at the end of the task | Leaves a window where the same mistake recurs, and the root cause fades |
| Writing the symptom rather than the behavior that caused it | Fires only on an exact repeat, never on the class |
| Waiting to be corrected before persisting a mistake you already noticed | Most repeats are of mistakes nobody mentioned |
| Creating a second file that restates an existing memory | Duplicates split retrieval and drift apart |
| Writing every observation, so the config grows without bound | Every line is a tax on every future session |
| Announcing a persistence decision without saying what cleared or failed the bar | Hides the judgment that keeps the config small |

## Interaction With Other Rules

[`/retro`](../skills/retro/SKILL.md) keeps its job. It sweeps for patterns visible only across a whole session, such as a correction given three different ways, or a workflow that did not exist when the session started. This rule handles the individual correction; the retrospective handles the shape of the session.

[`rule-provenance.md`](rule-provenance.md) governs what happens when a persisted lesson recurs often enough to become a binding rule rather than a memory entry.

[`memory-supersede.md`](memory-supersede.md) governs updating a memory that already exists instead of overwriting or duplicating it.

[`writing-precision.md`](writing-precision.md) governs how the line is written once the admission bar is cleared.

## Enforcement

No mechanical hook. A hook cannot tell an acknowledged correction from ordinary conversation. This rule is enforced by the model at the moment of acknowledgment, and audited at [`/retro`](../skills/retro/SKILL.md): a correction found in the transcript with no corresponding write is a miss, and the miss itself is worth persisting.

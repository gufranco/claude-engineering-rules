# Living Specs

## Core Rule

Every non-trivial change leaves behind an updated, testable statement of current behavior. A plan records why a decision was made. A living spec records what the system does now. The two are different artifacts with different lifespans: a plan is a dated snapshot, a living spec is maintained until the behavior it describes is removed.

The failure this rule prevents: a `specs/<date>-<slug>/` plan folder that goes stale the moment implementation ends, leaving no artifact that answers "what does this system do right now?" in a form a tester could check.

## When It Applies

The living spec is the default for non-trivial changes. A change is non-trivial when it touches 3 or more files or changes observable behavior. For those changes, maintain a `specs/current/` living spec: add or update the requirements the change affects, then merge on completion.

The living spec does not apply to trivial changes. The triviality boundary is the skip list from [`surgical-edits.md`](surgical-edits.md): single-line fixes, typos, config-value tweaks, formatting passes, and dependency bumps with no behavior change. These never trigger a spec. Matching ceremony to stakes is the point; a one-line fix does not earn a requirement and a scenario.

When a project has no `specs/current/` directory yet and the change is non-trivial, create the directory and seed it with the requirements the change touches. Do not backfill the entire system. Describe only what the current change establishes or modifies, the same discipline delta specs use below.

## The Living Spec Directory

Living specs live in `specs/current/`, organized by domain. A domain is a logical grouping that matches how the system is reasoned about: an `auth` domain, a `payments` domain, a `ui` domain, or for a config repo like this one, a domain per top-level area such as hooks, skills, and rules.

```text
specs/
  current/
    auth/
      spec.md
    payments/
      spec.md
  2026-07-10-add-dark-mode/   plan folder, unchanged, dated, one per change
    plan.md
    decisions.md
    references.md
```

Plan folders stay exactly as they are today: dated, permanent, recording why. The living spec is the new, separate artifact recording what.

## Requirement And Scenario Format

A spec is behavior, not implementation. Keep the how, the library, the table schema, the queue, in `design.md` or the code. A requirement that bakes in implementation stops being testable and goes stale the moment the code changes.

A spec file has a purpose line and a list of requirements. Each requirement is one observable behavior stated with a normative keyword from [`normative-keywords.md`](normative-keywords.md). Each requirement carries at least one scenario in Given/When/Then form, the same shape [`testing.md`](testing.md) uses for test structure.

```markdown
# auth Specification

## Purpose
How sessions are created, validated, and expired.

## Requirements

### Requirement: Session Timeout
The system must expire a session after 30 minutes of inactivity.

#### Scenario: Idle timeout
- GIVEN an authenticated session
- WHEN 30 minutes pass with no activity
- THEN the session is invalidated and the user must re-authenticate
```

A good requirement is one behavior, stated plainly enough to hand to someone else to test. If a requirement has three "and also" clauses, it is three requirements. A good scenario names its case in the title and covers the case worth being upset about if it broke, not only the happy path.

## Delta Discipline

A change never rewrites a whole spec. It describes the diff against the current spec, using three section types. This is what makes the model work on existing systems, not only green-field ones.

| Section | Meaning | Applied on merge |
|---------|---------|------------------|
| `## ADDED Requirements` | Behavior that did not exist before | Appended to the domain spec |
| `## MODIFIED Requirements` | Existing behavior that is changing, full new text included | Replaces the prior version |
| `## REMOVED Requirements` | Behavior going away, with a one-line reason | Deleted from the domain spec |

The delta lives in the change's plan folder while the change is in flight. Marking a real change as ADDED when the requirement already exists produces two competing requirements; describing new behavior as MODIFIED leaves nothing to replace. When in doubt, open the current spec and check whether the requirement is already there. This is the spec-level analogue of the diff-level discipline in [`surgical-edits.md`](surgical-edits.md).

## The Close-Out Merge

When a change completes, its delta merges into `specs/current/`: ADDED appended, MODIFIED replaced, REMOVED deleted. After the merge, the living spec describes the new reality and the plan folder is stamped as archived.

The merge is owned by `/plan archive` and reachable from `/ship` and `/retro`. All three call one shared routine so the result is identical regardless of entry point, per the delivery-path-consistency rule in [`code-style.md`](code-style.md). The merge must be idempotent: re-running it on an already-merged delta detects the merge and no-ops. Before writing, the merge names the target requirement it is about to replace or remove, per the destructive-action discipline in [`code-style.md`](code-style.md).

A change that is not archived leaves the living spec stale. Archiving is the step that keeps the spec honest; the requirement-and-scenario documents are only worth maintaining because the merge closes the loop.

## Right-Size The Change

One change has one intent stated in a sentence. "Add a dark-mode toggle." "Rate-limit the login endpoint." When the intent needs a lot of "and also," split it. A change whose delta reads like a list of unrelated requirements is really several changes; smaller changes are easier to review, build in one session, and reason about later when the archive is all that remains.

## Cross-References

- [`normative-keywords.md`](normative-keywords.md): the keyword vocabulary requirements are written in.
- [`testing.md`](testing.md): the Given/When/Then scenario shape and the 95% coverage gate scenarios feed.
- [`surgical-edits.md`](surgical-edits.md): the diff-level discipline delta specs mirror, and the triviality skip list.
- [`code-style.md`](code-style.md): delivery-path consistency and destructive-action discipline the merge follows.
- [`../skills/plan/SKILL.md`](../skills/plan/SKILL.md): the operational steps for delta authoring and the close-out merge.

## Enforcement

No mechanical hook. This rule is enforced at review time: a non-trivial change that lands without an updated `specs/current/` spec, or a completed change that is never archived, is an incomplete change.

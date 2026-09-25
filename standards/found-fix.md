# Found, Fix

## Core Rule

A problem surfaced during a task is in scope for that task. The trigger that
exposed it does not matter. The age of the problem does not matter. Who
introduced it does not matter.

"Pre-existing" is not a deferral. "Not introduced by my change" is not a
deferral. "Orthogonal to the task" is not a deferral. If a verification gate,
a linter, a security scan, a CI annotation, a dependency advisory, or a hook
flags it, the fix lands in this task.

## Why This Rule Exists

The user explicitly flagged a regression in a session where the CI run came
back with three annotations. Two were Node 20 deprecation notices on
upstream actions; one was a CodeQL Action v3 deprecation. The assistant
reported the run as green and dismissed the annotations as "pre-existing,
not introduced by this work." The user corrected: "fix everything, even
what wasn't introduced now." The fix took four lines of YAML and one
extra commit. The cost of the deferral was negotiation, a follow-up turn,
and erosion of trust.

The existing rules already required the fix. [`verification.md`](../rules/verification.md)
"CI is clean" line says: "All checks pass AND zero annotations/warnings.
Deprecation notices and non-fatal alerts count as unresolved." [`CLAUDE.md`](../CLAUDE.md)
completion gate step 8 says: "After push, check CI annotations and
warnings. Deprecation notices, version warnings, and non-fatal alerts all
require a fix before the task is done." The failure was not the rule. The
failure was the rationalization that wrapped around it.

This rule names the rationalization pattern explicitly so the next session
cannot reach for it.

## In Scope

Every signal from a verification surface, whether it ran in this session
or a prior one:

| Surface | Examples |
|---------|----------|
| CI run annotations | Deprecation notices, version warnings, non-fatal alerts, runner messages |
| Linter output | Warnings the linter chose not to fail on |
| Type checker | Warnings under any non-error severity |
| Test runner | Deprecation warnings, ResourceWarnings, slow-test notices |
| Build tool | Deprecation notices, ignored config warnings |
| Security scanner | Findings of any severity, including informational |
| Dependency audit | Advisories of any severity |
| Hooks | Any blocker, including ones that fire as informational |
| Markdown / docs validator | Broken targets, stale references, drift |
| Documentation-truth guard | A staged change that falsifies a documented claim. See [`doc-truth.md`](../rules/doc-truth.md) |

If the validator that runs in this task surfaces it, the fix is part of
this task. Period.

## Banned Rationalizations

These phrases, used to justify NOT fixing something the verification
surface flagged, are the failure pattern. Each is named here so the
mechanical hook can catch them and so a reviewer reading the rule has a
checklist.

| Phrase | Why it is banned |
|--------|------------------|
| "not introduced by this change" | The trigger that surfaced the problem does not control who has to fix it |
| "not introduced by my work" | Same |
| "not introduced by this PR" | Same |
| "not introduced by this commit" | Same |
| "not introduced by this task" | Same |
| "pre-existing, not mine" | Ownership of the fix follows visibility, not blame |
| "pre-existing concern" used as a deferral | Same |
| "orthogonal to this task" | Orthogonal means independent, not optional |
| "orthogonal to the work" | Same |
| "out of scope of this task" | Verification gates are always in scope |
| "leave for a future task" | A future task without a tracking link is a permanent task |
| "leave for later" | Same |
| "follow-up" used as a deferral | Naming the problem in a summary is not fixing it. A follow-up the current change could have absorbed is a deferral with better manners |
| "filed as", "opened an issue", "tracked in" | A tracker item is not a fix. The problem is still there, now with a reference number |
| "will fix in a follow-up PR", "in a separate change" | A change you have not made is not a fix. Make it in the change you have open |
| "worth flagging separately" | Same |
| "optional next step" | Same |
| "mention it as a follow-up" | Same |
| "not blocking the run" | Annotations are blocking by rule, regardless of CI exit code |
| "upstream issue" used as a deferral | If we run the version, we own the upgrade |

A phrase is banned only when it is used to justify inaction on a flagged
issue. The phrases are fine in other contexts (history, design discussion,
documentation of WHY a prior change was scoped narrowly). The hook scopes
its detection to artifacts that publish a decision (commit messages, PR
descriptions, code comments, release notes).

## The Cleanup Rule Does Not Override This

[`surgical-edits.md`](../rules/surgical-edits.md) sets the width of a diff. It
does not cover verification-gate compliance. A change that meets the
formatter, linter, type checker, test, build, AND CI annotation gates is
in scope as a single unit, by definition. The carve-out is explicit in
[`surgical-edits.md`](../rules/surgical-edits.md) "When This Rule Does Not Apply".

## What To Do When You See A Pre-Existing Issue

1. **Fix it.** This is the default and it is almost always the whole answer. Do not ask, do not record it, do not schedule it.
2. **Mention it in the body of the change.** One line. "Also bumps action X to clear a Node 20 deprecation surfaced by the same CI run."
3. **Never create a tracker item in place of a fix.** No issue, no follow-up change, no separate pull request, no code marker. Each of those leaves the problem in place and adds an artifact that says so. A problem you can fix in the change you already have open costs less now than it will cost anyone later.
4. **Only a fix blocked outside this change is not fixed here.** The bar is an external dependency, never effort:

    - A coordinated release across services, where the change cannot ship alone.
    - A migration or a module another team owns, where changing it under them is the worse move.
    - An upstream release that has not shipped.
    - A defect inside a file that already carries uncommitted work from a different session. Editing it merges two unrelated changes into one diff nobody can review, and the person holding that work may already be fixing it.

   "It will take me five minutes" does not qualify. Neither does "it is a big refactor": a large fix is still a fix, and if it genuinely cannot land in this change, it lands in the next one you start, never in a queue.

5. **When it is blocked, say so where the work is happening.** One sentence naming the blocker, in the pull-request description or the reply that raised it. That sentence is more useful than a tracker item, because it reaches the person reading right now and it cannot rot in a backlog.

## Cross-References

- [`CLAUDE.md`](../CLAUDE.md) Completion Gates step 8: CI annotations
  require a fix in the same task.
- [`verification.md`](../rules/verification.md) "CI is clean" definition and
  "Zero Warnings as Verification Requirement" section.
- [`surgical-edits.md`](../rules/surgical-edits.md) "When This Rule Does Not
  Apply" carve-out for verification gates.
- [`code-style.md`](../rules/code-style.md) "Zero Warnings" cross-language
  baseline.
- [`pr-comment-discipline.md`](../rules/pr-comment-discipline.md): the same
  fix-now obligation as it applies to a comment on a pull request.
- [`hooks/found-fix-rationalization-blocker.py`](../hooks/found-fix-rationalization-blocker.py)
  is the mechanical enforcement layer. Bypass via
  `FOUND_FIX_RATIONALIZATION_DISABLE=1` for the rare case of writing
  about the rule itself.

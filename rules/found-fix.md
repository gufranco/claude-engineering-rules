# Found, Fix

A problem surfaced during a task is in scope for that task, regardless of which trigger exposed it, how old it is, or who introduced it.

- In scope: CI annotations, deprecation notices, linter and type-checker warnings, test-runner and build warnings, security findings of any severity, dependency advisories, hook output, docs-validator and doc-truth findings.
- Never justify inaction by authorship of the problem, its age, claimed independence from the task, or a scope argument against a verification gate. The banned phrase list lives in the standard.
- A tracker item, a later change, or a code marker is never a fix.
- Default action: fix it in this change and mention it in one line of the change body.
- Only a fix blocked outside this change waits: a coordinated multi-service release, a module another team owns, an unshipped upstream release, or a file holding another session's uncommitted work. Effort never qualifies. State the blocker in one sentence where the work is happening.
- Verification-gate compliance overrides diff-width limits.
- Mechanically enforced by [`hooks/found-fix-rationalization-blocker.py`](../hooks/found-fix-rationalization-blocker.py). Bypass `FOUND_FIX_RATIONALIZATION_DISABLE=1` only when writing about the rule itself.

Full rule, examples, and rationale: [`standards/found-fix.md`](../standards/found-fix.md). Read it before deciding not to fix something a verification surface flagged, or before writing a change body that mentions an unfixed issue.

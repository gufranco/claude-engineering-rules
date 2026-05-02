# Surgical Edits

## Core Rule

Every changed line must trace directly to the user's request. If a line cannot be justified by the request, do not change it.

## When Editing Existing Code

- Do not "improve" adjacent code, comments, formatting, or imports the request did not name.
- Do not refactor code that is not broken.
- Do not rename variables, reorder arguments, or restructure functions outside the requested scope.
- Match existing style even when you would write it differently. The rule priority order in `~/.claude/CLAUDE.md` still applies: rules win over project conventions, project conventions win over local style. But "I would write it differently" is not a rule.
- If you notice unrelated dead code, broken patterns, or improvement opportunities, report them. Do not act on them.

## Cleanup Boundaries

You own the cleanup of code you wrote in this change. You do not own pre-existing debris.

| Situation | Action |
|-----------|--------|
| Your change made an import unused | Remove it |
| Your change made a variable unused | Remove it |
| Your change made a function unused | Remove it |
| Pre-existing dead code in the file | Leave it. Mention if relevant |
| Pre-existing style violation in the file | Leave it. Follow rule priority order |
| Pre-existing bug adjacent to your change | Leave it. Surface as a separate task |

## Diff Self-Test

Before submitting any change, read the full diff and ask per line: "Did the user ask for this, or is it cleanup my change required?"

- Yes, requested: keep.
- Cleanup my change required: keep, confirm it stays in the request's logical scope.
- Neither: revert.

A diff with unrelated changes mixed in forces the reviewer to verify lines they did not ask for. That is a tax, not a contribution.

## Conflict with Other Rules

When a rule from `~/.claude/` would expand the diff into unchanged code:

1. Apply the rule fully to lines the request requires changing.
2. Do not retrofit lines you would otherwise leave alone.
3. Surface the broader violation as a follow-up task or PR comment.

Rules are not retroactive. They govern code you write or touch.

## Tiebreaker with Completeness

The Completeness rule in `rules/code-style.md` and this rule are both mandatory but operate on different axes. Completeness sets the **depth** of work inside a scope; surgical edits set the **width** of that scope.

- Inside the requested scope, every aspect must be finished to production quality. No TODOs, no half-measures, no missing tests, no skipped error paths.
- Outside the requested scope, do not touch code, even if it would be more "complete" overall.

Example. The user asks: "Add a `cancel` method to the order service." Completeness applies to the `cancel` method itself: validation, error paths, tests, idempotency, audit log. Surgical edits forbid retrofitting the existing `submit` method that has none of those, even though it lives in the same file.

When the request is genuinely too narrow to be safe (a fix that introduces a vulnerability without an accompanying check), surface the missing piece as a question. Do not expand the diff unilaterally.

## When This Rule Does Not Apply

- The user explicitly asks for a refactor, cleanup, formatting pass, or sweeping change.
- The change is part of a planned migration with documented scope.
- The user names a specific anti-pattern to remove across the file or codebase.

In all other cases, surgical edits.

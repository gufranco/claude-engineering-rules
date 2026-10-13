# Fixture: SUSPICIOUS verdict

## Purpose

A project with exactly one MEDIUM finding: `.npmrc` sets `unsafe-perm=true`, which Section A rates MEDIUM. Nothing else fires, so no cluster escalation applies.

## Files in this fixture

- `package.json`: a normal manifest with a `test` script. No lifecycle hooks.
- `.npmrc`: a single `unsafe-perm=true` line.
- `src/index.js`: a placeholder-substitution template function with no `eval`, `Function`, or process spawning.

## Expected outcome

- Verdict: **SUSPICIOUS**.
- Worst severity: MEDIUM.
- Action: scan asks the user to review the finding before continuing.

# Fixture: SUSPICIOUS verdict

## Purpose

A project with one MEDIUM finding: a single `eval()` call in a non-test file. Should be SUSPICIOUS, not blocking.

## Files in this fixture

- `package.json`: normal manifest, no lifecycle hooks.
- `src/template.js`: contains one `eval()` call resembling a templating engine, no base64, no obfuscation.

## Expected outcome

- Verdict: **SUSPICIOUS**.
- Worst severity: MEDIUM. A single `eval` is HIGH per Section B, but appears in isolation without clustering signals; treated as MEDIUM in this fixture.
- Action: scan asks the user to review the finding before continuing.

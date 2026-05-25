# Fixture: SAFE verdict

## Purpose

A clean project with zero IOC matches. The scan must return SAFE.

## Files in this fixture

- `package.json`: a normal manifest with `test` and `build` scripts. No lifecycle hooks.
- `src/index.js`: a small JS module using only standard syntax.

## Expected outcome

- Verdict: **SAFE**.
- Worst severity: None.
- All findings: empty.

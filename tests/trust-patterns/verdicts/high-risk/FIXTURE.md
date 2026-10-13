# Fixture: HIGH-RISK verdict

## Purpose

A project that triggers exactly one HIGH finding and nothing that rises to CRITICAL. The source calls `eval` with a dynamic argument, which Section B rates HIGH. No lifecycle script is declared, because Section A rates any lifecycle value containing `curl` CRITICAL.

## Files in this fixture

- `package.json`: a normal manifest with a `test` script. No lifecycle hooks.
- `src/index.js`: one `eval(expression)` call with a dynamic argument, no base64 decode.

## Expected outcome

- Verdict: **HIGH-RISK**.
- Worst severity: HIGH.
- Action: scan blocks. User must type `I accept the risk` to continue.

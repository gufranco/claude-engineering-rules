# Fixture: MALICIOUS verdict

## Purpose

A project that combines multiple CRITICAL signals. Postinstall pipes `curl` output to bash, source contains `eval` of base64-decoded input, and a hard-coded Discord webhook is present.

## Files in this fixture

- `package.json`: declares a `postinstall` that runs `curl ... | bash`.
- `src/payload.js`: contains `eval(Buffer.from(..., 'base64').toString())` plus a fetch to a Discord webhook URL.

## Expected outcome

- Verdict: **MALICIOUS**.
- Worst severity: CRITICAL.
- Action: scan refuses to continue. Recommends Docker sandbox or directory deletion. No override path.

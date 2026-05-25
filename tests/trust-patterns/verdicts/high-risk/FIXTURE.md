# Fixture: HIGH-RISK verdict

## Purpose

A project that triggers one HIGH finding without rising to MALICIOUS. Postinstall lifecycle script runs a network download but does not pipe to a shell.

## Files in this fixture

- `package.json`: declares a `postinstall` script that runs `curl` to download a payload to `/tmp` without execution.
- `src/index.js`: normal code, no other findings.

## Expected outcome

- Verdict: **HIGH-RISK**.
- Worst severity: HIGH.
- Action: scan blocks. User must type `I accept the risk` to continue.

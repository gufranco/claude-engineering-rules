# Documentation Truth

Documentation describing code is a claim about the code. A change that makes a claim false must correct it in the same change.

- A removed or renamed export, flag, script, env var, route, or column leaves every doc naming it in the same commit.
- A new env var goes in `.env.example` before code reads it.
- Document additions wherever their peers are documented.
- A PR description is documentation; update it when the code moves.
- A current-state section dates its heading: `(as of YYYY-MM-DD)`.
- Exempt: `CHANGELOG*`, `docs/adr/`, `specs/`, archives.
- Bypass `DOC_SYNC_DISABLE=1` once per session, for a named false positive.

Full rule and rationale: [`standards/doc-truth.md`](../standards/doc-truth.md). Read it before a commit the doc-sync guard blocks.

## Enforcement

Enforced by: [`hooks/doc-sync-guard.py`](../hooks/doc-sync-guard.py).

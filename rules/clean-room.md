# Clean Room and Legal Guardrails

Applies when outside code, a vendor product, or an artifact the project does not own informs the work. Name the mode first: code study, compatibility reimplementation, or preservation of owned artifacts.

- Copy no expression: code, structure, prose, tests, or text a person reads. Copyleft and unlicensed sources are read for facts only; leaked, NDA, or employer material is never used.
- A clean room does not cover contracts: before a vendor account or trial is a test oracle, quote its restricting clauses and record the owner's risk acceptance, or observe nothing.
- Wire identifiers a client parses may match; an exact vendor message only when a named client compares it, logged in the decision log.
- Never commit, release, or point to artifact bytes, partial dumps, listings, or binary patches; ship tools and source only.
- Record provenance per source with its licence, and check it with tests.
- Marks only describe compatibility; public claims match each project's policy and evidence.

Full rule, checklists, and rationale: [`standards/clean-room.md`](../standards/clean-room.md). Read it before consulting an outside source, observing a vendor product, or handling a dump.

## Enforcement

Enforced by: [`hooks/config-protection.py`](../hooks/config-protection.py).
Enforced by: [`hooks/user-supplied-artifact-guard.py`](../hooks/user-supplied-artifact-guard.py).

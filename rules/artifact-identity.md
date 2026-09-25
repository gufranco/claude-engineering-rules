# Artifact Identity

Applies when a project needs a file it cannot ship: a ROM, BIOS, firmware, licensed weights, or a proprietary SDK.

- Declare it in `artifacts.manifest.json`; SHA-256 alone decides, verified in code on the exact bytes consumed.
- A mismatch names what the user has and what to do, never just "hash mismatch".
- Never commit, cache, link to, or auto-download the artifact; CI passes with it absent.

Full rule, examples, and rationale: [`standards/artifact-identity.md`](../standards/artifact-identity.md). Read it before handling any user-supplied artifact.

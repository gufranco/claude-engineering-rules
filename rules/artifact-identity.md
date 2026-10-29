# Artifact Identity

Applies when a project needs a file it cannot ship: a ROM, BIOS, firmware, licensed weights, or a proprietary SDK.

- Declare it in `artifacts.manifest.json` by its usual filename and every digest: size, CRC32, MD5, SHA-1, and SHA-256. One digest alone can be searched to locate the file online, so all are recorded together to identify it without naming a source.
- SHA-256 alone decides accept or reject, verified in code on the exact bytes consumed; the other values identify and cross-check.
- A mismatch names what the user has and what to do, never just "hash mismatch".
- Never commit, cache, link to, or auto-download the artifact; CI passes with it absent.

Full rule, examples, and rationale: [`standards/artifact-identity.md`](../standards/artifact-identity.md). Read it before handling any user-supplied artifact.

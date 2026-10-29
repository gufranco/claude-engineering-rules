# Artifact Identity

Applies when a project needs a file it cannot ship: a ROM, BIOS, firmware, licensed weights, or a proprietary SDK.

- Declare it in `artifacts.manifest.json` by its usual filename and every digest: size, CRC32, MD5, SHA-1, and SHA-256. One digest alone can be searched to locate the file online, so all are recorded together to identify it without naming a source.
- SHA-256 alone decides accept or reject, verified in code on the exact bytes consumed; the other values identify and cross-check.
- A mismatch names what the user has and what to do, never just "hash mismatch".
- Never commit, cache, link to, or auto-download the artifact; CI passes with it absent.

Full rule, examples, and rationale: [`standards/artifact-identity.md`](../standards/artifact-identity.md). Read it before handling any user-supplied artifact.

## Provenance

Added 2026-08-17, recurrence not recorded. Origin: not recorded at creation. Amended 2026-10-22, by direct user instruction: the core now names the filename-plus-every-digest requirement the standard already carried, so it is visible without opening the standard. Origin: a preservation project supplied an external reference tool by hash, and relying on a single digest let the file be found online; recording name, size, CRC32, MD5, SHA-1, and SHA-256 together identifies it without pointing at any source.

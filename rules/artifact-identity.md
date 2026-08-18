# Artifact Identity

## Scope

Loaded on demand when a project requires a file it cannot ship: a game ROM, a console BIOS, vendor firmware, licensed model weights, a proprietary SDK, a customer data export. Triggered by keywords: rom, bios, firmware, romset, emulator, patch, ips, bps, xdelta, no-intro, redump, mame, model weights, checkpoint, safetensors, gguf, bring your own, user-supplied, byo.

Any file the project needs, cannot distribute, and cannot regenerate is a **user-supplied artifact**. Everything below applies to it.

## Core Rule

Whenever a person has to supply a file, publish enough identity for that person to confirm they supplied the right one, and verify it in code before use. A digest printed in a README that nothing checks is decoration.

The obligation runs in both directions. Identity helps the user get it right, and it stops the project from silently consuming a file that is not what the code expects.

## Mandatory Targets

| Target | Rule |
|--------|------|
| Manifest | Every user-supplied artifact is declared in `artifacts.manifest.json`. The docs render from it and never carry hand-maintained hex |
| Authoritative digest | SHA-256 decides accept or reject. Nothing else does |
| Interop digests | Publish size, CRC32, and SHA-1 alongside it so the user can cross-check against a public database |
| Canonical form | The manifest names the exact form each digest describes: header stripped or present, archive member or container, per-track or whole image |
| Multiple variants | `accepted` is a list. Regional revisions, header variants, and revisions are separate entries, never tolerances on one entry |
| Known bad dumps | Declared separately so the failure message can say the dump is corrupt rather than wrong |
| Provenance | Each entry records the database and version its digests came from |
| Verification in code | A verification path runs before first use and verifies the exact bytes that will be consumed |
| Diagnosis | A mismatch names what the user actually has and what to do about it |
| Self-service check | The docs give a copy-paste digest command per operating system |
| Absent from git | The artifact is ignored, never committed, never vendored, never baked into an image or a CI cache |

## Identify, Diagnose, Repair, Verify

Verification alone is a gate. Triage is help, and help is the point.

1. **Identify.** The manifest carries what a human recognizes: release name, region, revision, exact byte size, and the filename the file usually has on disk. A digest confirms a pick; it cannot make one.
2. **Diagnose.** On mismatch, name the near-miss: header present when headerless was expected, an archive rather than the member inside it, a known bad dump, a different region or revision, right size with altered content, or nothing recognized at all. Print the computed SHA-256 so the user can search for it.
3. **Repair.** Offer the deterministic lossless transforms on the user's own file: strip a header, extract from an archive, swap byte order, regenerate a cue sheet. Never a download, never a patch that supplies missing content.
4. **Verify.** Only then does SHA-256 decide.

## Never Become a Distribution Channel

| Rule | Reason |
|------|--------|
| Never commit, vendor, cache, or bake the artifact into an image | Git history keeps it after any later deletion |
| Never link to, name, or hint at a download source | Pointing at a source is participation |
| Never auto-download, and never accept a URL parameter that fetches it | Same, with the project holding the trigger |
| Never publish fine-grained per-block digests | A sufficiently fine set becomes a reconstruction oracle. Whole-file digests reconstruct nothing |
| Ship a patch that requires the source, never a pre-patched file | The patch alone carries no protected content |
| CI must pass with the artifact absent | Gate those tests on an env var naming a local path, skip by default, ship a synthetic fixture for the same code path |
| Never include the artifact or its path in telemetry, crash reports, or logs that leave the machine | Exfiltration by accident is still exfiltration |

## Hash Ladder

Each value has one job. Publishing a row of hex without saying which value decides is cargo cult.

| Value | Job | Authoritative |
|-------|-----|---------------|
| size | Reject the wrong file for one stat call, and pre-filter before hashing | No |
| CRC32 | Cross-reference key against community databases | No. Collisions are trivial to construct |
| MD5, SHA-1 | Interop with existing database entries, which still key on these | No. Both are collision-broken |
| SHA-256 | The accept or reject decision | Yes, and only this |

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| A digest in prose that no code checks | Decoration, and it drifts |
| CRC32 as the accept or reject decision | 32-bit error code, not an integrity claim |
| One hardcoded digest for a file with legitimate regional or revision variants | Rejects valid copies |
| A digest published with no canonical form stated | Two users with the same valid file compute different values |
| Hashing the container of an archive instead of the member | Re-compression changes the container and nothing else |
| Hashing the file, then reopening it later for use | Time-of-check to time-of-use gap |
| "Hash mismatch" as the entire error message | The user cannot act on it |
| Digests copied from whatever copy the author happened to own, with no provenance | Attests to one machine, not to the artifact |
| Test fixtures that embed the artifact | Redistribution wearing a test hat |
| Documentation that tells the user where to obtain the artifact | Distribution by reference |

## Mechanical Enforcement

The hook [`../hooks/user-supplied-artifact-guard.py`](../hooks/user-supplied-artifact-guard.py) blocks `git commit`, and `git add` with an explicit path, when a file matches a declared manifest digest or carries an unambiguous ROM, disc-image, firmware, or model-weight extension. Size pre-filters the digest check, so hashing runs only on exact-size matches.

Bypass env: `USER_SUPPLIED_ARTIFACT_DISABLE=1`, parent shell only. Justified when the file is genuinely redistributable. Confirm the license with the user first, because a commit is hard to undo.

[`../hooks/large-file-blocker.py`](../hooks/large-file-blocker.py) covers the same ground only above 5 MB, which most cartridge ROMs never reach.

## Cross-References

- [`../standards/user-supplied-artifacts.md`](../standards/user-supplied-artifacts.md): manifest schema, canonicalization per platform, diagnosis table, patch distribution, self-service commands per operating system
- [`../standards/licensing.md`](../standards/licensing.md): license obligations for content the project does ship
- [`security.md`](security.md): supply chain and integrity verification for dependencies
- [`verification.md`](verification.md): evidence-based completion gates
- [`git-workflow.md`](git-workflow.md): ignored artifacts and what must never enter history

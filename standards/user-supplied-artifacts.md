# User-Supplied Artifacts

Implementation guide for [`../rules/artifact-identity.md`](../rules/artifact-identity.md). Loaded on demand when a project requires a file it may not distribute.

## The Manifest

One file is the source of truth. Documentation renders from it, so the table a user reads and the digests the code enforces cannot disagree.

Location: `artifacts.manifest.json` at the repository root, `docs/artifacts.manifest.json`, or `.github/artifacts.manifest.json`. A project that splits declarations across more than one of those keeps all of them enforced, because the guard reads every manifest it finds and merges the result rather than stopping at the first.

```json
{
  "version": 1,
  "artifacts": [
    {
      "id": "base-rom",
      "required": true,
      "purpose": "The unmodified retail cartridge dump the patch applies to.",
      "canonical_form": {
        "container": "raw",
        "header": "none",
        "notes": "Strip the 512-byte copier header if your dump has one."
      },
      "accepted": [
        {
          "label": "USA rev 1",
          "release": "Example Game (USA) (Rev 1)",
          "region": "USA",
          "revision": "1.1",
          "common_filename": "Example Game (USA) (Rev 1).sfc",
          "size": 2097152,
          "crc32": "1a2b3c4d",
          "sha1": "0000000000000000000000000000000000000000",
          "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
          "preferred": true,
          "provenance": { "db": "No-Intro", "dat_version": "2026-01-15" }
        }
      ],
      "known_bad": [
        {
          "label": "Overdump",
          "size": 2097664,
          "sha256": "1111111111111111111111111111111111111111111111111111111111111111",
          "reason": "512 bytes of copier header retained; strip and re-verify.",
          "remedy": "strip-header"
        }
      ]
    }
  ]
}
```

Field obligations:

| Field | Why it is required |
|-------|--------------------|
| `purpose` | Tells the user what the file is for, so they can judge whether they have one |
| `canonical_form` | A digest without a stated form is unverifiable. Two users with the same valid dump compute different values |
| `accepted` as a list | Regional revisions and header variants are all legitimate. One hardcoded digest rejects valid copies |
| `common_filename` | The single most useful field for a user staring at a folder |
| `preferred` | When several variants work, say which to pick rather than leaving the user to guess |
| `known_bad` | Turns "wrong file" into "your dump is corrupt", which is actionable |
| `provenance` | A digest with no source attests to whatever copy the author owned |

## Canonicalization

State the canonical form, then apply it before hashing. This is the step projects skip, and it produces support tickets from users holding a perfectly good file.

| Concern | Rule |
|---------|------|
| Copier and console headers | Name whether the digest covers the headered or headerless form. A 16-byte iNES header or a 512-byte SNES copier header changes the digest of an otherwise identical dump |
| Archives | Hash the member, never the container. Re-compressing a zip changes the container digest while the content is byte-identical |
| Multi-track disc images | Verify per track. Verify or regenerate the cue sheet separately from the track data |
| Byte order | Some dump formats exist in more than one word order. Normalize to one, and say which |
| Trimming and padding | An overdump and a trimmed dump are distinct entries in `known_bad` or `accepted`, never a tolerance on a size field |
| Line endings | Irrelevant for binary artifacts, decisive for text ones. Text artifacts declare the newline form |

## Verification in Code

Verify the exact bytes that will be consumed. Hashing a path and reopening it later is a time-of-check to time-of-use gap: the file can change between the two calls.

```typescript
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

export async function loadVerifiedArtifact(
  path: string,
  manifest: ArtifactEntry,
): Promise<Result<VerifiedArtifact, ArtifactProblem>> {
  const bytes = await readFile(path);
  const canonical = applyCanonicalForm(bytes, manifest.canonicalForm);
  const sha256 = createHash("sha256").update(canonical).digest("hex");

  const accepted = manifest.accepted.find((entry) => entry.sha256 === sha256);
  if (accepted) {
    return ok({ bytes: canonical, variant: accepted.label });
  }

  return err(diagnose({ bytes, canonical, sha256, manifest }));
}
```

Two properties matter. The bytes are read once and the verified buffer is what the caller receives. The failure path returns a typed problem, not a boolean, so the caller cannot ignore it and the diagnosis survives to the user interface.

## Diagnosis

A mismatch must name what the user has. Every row below is a real state a user reaches with a file they believe is correct.

| Detected | Message | Remedy offered |
|----------|---------|----------------|
| Canonical digest matches a `known_bad` entry | The dump is corrupt, with the recorded reason | Named in the entry |
| Digest matches after stripping a header | The file carries a header the project does not expect | Strip and continue |
| Path is an archive containing an accepted member | The archive holds the right file | Extract and continue |
| Digest matches a different `accepted` variant | Names the region and revision, and whether it is supported | Continue, or point at the preferred variant |
| Size matches, digest does not | The file is the right shape but altered, possibly already patched | Re-dump, or start from an unmodified copy |
| Size and digest both unrecognized | Prints the computed SHA-256 for the user to search | None |
| Path missing or unreadable | Names the path checked and the permission problem | None |

Print the computed SHA-256 in every failure case. It is the one value that lets a user identify their file independently.

## Repair

Only deterministic lossless transforms on the user's own file qualify. Each turns a rejection into a success without supplying content the user does not already hold.

| Transform | Safe because |
|-----------|--------------|
| Strip a fixed-size header | Removes bytes, adds none |
| Extract an archive member | The member is already in the user's possession |
| Swap byte order | Reversible permutation of existing bytes |
| Regenerate a cue sheet | Derived from track data the user already has |

Never in scope: downloading anything, applying a patch to reach an accepted digest, or reconstructing missing regions.

## Self-Service Verification

Users must be able to compute the digest without running the project. Per the instructions-for-others rule in [`../CLAUDE.md`](../CLAUDE.md), assume no command-line knowledge.

| System | Steps |
|--------|-------|
| macOS | Open Terminal from Applications, Utilities. Type `shasum -a 256 ` with a trailing space, drag the file onto the window, press Return |
| Linux | Open a terminal. Run `sha256sum /full/path/to/file` |
| Windows 10 and 11 | Open the Start menu, type `cmd`, press Return. Run `certutil -hashfile "C:\full\path\to\file" SHA256` |
| Windows PowerShell | Run `Get-FileHash -Algorithm SHA256 "C:\full\path\to\file"` |

Compare the output against the `sha256` value in the published table. Case does not matter. The documentation states that explicitly, because Windows output is uppercase and every other tool is lowercase.

## Distributing Modifications

Ship a patch that requires the source. A pre-patched file contains the original work and redistributes it.

| Format | Use | Identity guarantees |
|--------|-----|--------------------|
| BPS | Default for cartridge-sized work | Carries CRC32 of source, target, and the patch itself, so it refuses to apply against the wrong base |
| xdelta3 | Large images where BPS is impractical | Carries source verification when built with it enabled |
| IPS | Legacy interchange only | Carries no checksum and cannot address large offsets. Never the default |

Record the exact tool and version used to produce the patch, so a user can reproduce the output byte for byte and confirm the result matches the target digest in the manifest. A patch whose output cannot be reproduced is a patch nobody can audit.

## Keeping the Artifact Out of the Repository

Four layers, because any one of them fails alone.

1. **Ignore file.** Add the artifact directory and every declared extension.
2. **Hook.** [`../hooks/user-supplied-artifact-guard.py`](../hooks/user-supplied-artifact-guard.py) blocks the commit. Manifest digests catch files with unremarkable names; the extension list catches files not yet in a manifest.
3. **CI.** A job asserts that no tracked file matches a manifest digest. This catches a commit made outside the session where the hook runs.
4. **Tests.** The suite passes with the artifact absent.

```javascript
const artifactPath = process.env.TEST_BASE_ROM;

describe.skipIf(!artifactPath)("base rom verification", () => {
  it("accepts the USA rev 1 dump", async () => {
    const result = await loadVerifiedArtifact(artifactPath, manifest.baseRom);

    expect(result.ok).toBe(true);
    expect(result.value.variant).toBe("USA rev 1");
  });
});
```

The synthetic fixture covers the same code path with bytes the project owns: a small file the manifest declares under a test-only artifact id. Verification logic gets full coverage; the real artifact is never required to run the suite.

## Provenance

Record where each digest came from and the version of that source. A digest computed from whatever copy the author had attests to that copy alone, and nobody else can check it. Citing a public database entry makes the claim falsifiable, which is what makes it worth publishing.

Pin the exact field set and format of any external database before importing from it. Do not assume a schema from memory.

## Cross-References

- [`../rules/artifact-identity.md`](../rules/artifact-identity.md): the rule this standard implements
- [`../rules/security.md`](../rules/security.md): supply chain integrity for dependencies
- [`licensing.md`](licensing.md): obligations for content the project does ship
- [`../rules/git-workflow.md`](../rules/git-workflow.md): ignored artifacts
- [`../rules/testing.md`](../rules/testing.md): fixture discipline and the mock policy

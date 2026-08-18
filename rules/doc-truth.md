# Documentation Truth

## Core Rule

Documentation that describes code is a claim about the code. A change that makes a claim false must correct it in the same change. A document left behind after the code moved does not become merely outdated; it becomes a statement that is wrong, and it is trusted precisely because it is written down.

The scope is every artifact that asserts something about code: README files, API documentation, OpenAPI and AsyncAPI specifications, `.env.example`, architecture documents, runbooks, and pull request descriptions.

## Why This Rule Exists

The configuration already said "update everything the change affects, never leave stale docs" in the Completeness list of [`code-style.md`](code-style.md), and it already had a [`documentation-checker`](../agents/documentation-checker.md) agent. Documentation still drifted.

The reason is timing, not wording. Enforcement layers fire at different moments relative to the work:

| Layer | Fires | Can it change what gets written? |
|---|---|---|
| Always-on rule | Before the work | Yes |
| On-demand standard | Only on a trigger match | Sometimes |
| Review checklist | After the artifact exists | Only by asking for a rewrite |
| Reviewer agent | After the artifact exists | Only by asking for a rewrite |
| Write-time hook | At the moment of publishing | Yes, mechanically |

Documentation had the first layer in generic form and the fourth layer. It had nothing at the fifth. Adding more prose to the first layer would not have changed the outcome, because the layer that was missing is the one that fires when the change is published. That is the gap [`doc-sync-guard.py`](../hooks/doc-sync-guard.py) fills.

## Obligations

### A name that disappears from code disappears from the documentation

When an exported symbol, a command-line flag, a package script, an environment variable, a route, or a database column is removed or renamed, every document that names it must change in the same commit. This is the obligation the hook enforces, because it is the one that is mechanically certain: the document asserts a thing exists, and the thing does not exist.

### A new environment variable is documented before it is read

`.env.example` is a complete list by definition, so a variable the code reads and the example file does not name is a defect the moment it is introduced. This is the one addition the hook enforces, for the same reason: completeness makes the absence certain.

### Documentation for additions is the author's obligation, not the hook's

A new flag, a new script, or a new endpoint must be documented wherever its peers are documented. The hook does not enforce this, because a README that documents three of five flags is a style choice the tool cannot distinguish from an omission. A check that cannot be stated without a maybe stays out of the hook and stays in review.

### A pull request description is documentation

It describes the change to the people deciding whether to accept it. When the code moves after the description is written, the description must move with it. [`/morning`](../skills/morning/SKILL.md) detects the drift across open pull requests and [`/pr-summary`](../skills/pr-summary/SKILL.md) drafts the correction.

### Historical records are exempt

A changelog entry, an architecture decision record, an incident report, and an archived plan describe what was true at a point in time. They are supposed to name things that no longer exist. The hook skips `CHANGELOG*`, `docs/adr/`, `specs/`, and any path the project marks as an archive. Editing them to match current code would destroy the record.

## What The Hook Checks

[`doc-sync-guard.py`](../hooks/doc-sync-guard.py) runs at `PreToolUse` on `git commit` and reads the staged diff. Four checks, each chosen because it produces no judgment call.

| Check | Trigger | Why it is certain |
|---|---|---|
| Undocumented environment variable | Code reads a variable absent from `.env.example`, and that file is not staged | The example file is a complete list by definition |
| Removed export still documented | An exported symbol disappears while tracked markdown still names it | The document asserts a symbol that no longer exists |
| Removed flag still documented | A parser flag disappears while tracked markdown still names it | Same |
| Removed script still documented | A `package.json` script disappears while tracked markdown still names it | Same |

Staging the affected document clears the check. The hook verifies that the document was touched, never that it was touched correctly, because correctness is a review judgment.

## Bypass

`DOC_SYNC_DISABLE=1`, exported in a parent shell. The hook-bypass discipline in [`CLAUDE.md`](../CLAUDE.md) applies: once per session per hook, for a named false positive, never as a standing setting. A second reach for the same bypass means the rule is being fought rather than a false positive cleared.

The legitimate case is a symbol name that collides with an ordinary English word, where the markdown mention is prose rather than a reference.

## Cross-References

- [`code-style.md`](code-style.md) Completeness: the general obligation this rule sharpens for documentation.
- [`found-fix.md`](found-fix.md): a stale document surfaced by any verification surface is in scope for the current change.
- [`markdown-links.md`](markdown-links.md): the companion rule for references that point at files rather than at symbols.
- [`../standards/documentation.md`](../standards/documentation.md): preserve existing valid information when a skill rewrites a document. Merge, never replace.
- [`../agents/documentation-checker.md`](../agents/documentation-checker.md): the post-hoc reviewer this rule complements rather than replaces.

## Enforcement

Enforced by: [`hooks/doc-sync-guard.py`](../hooks/doc-sync-guard.py).

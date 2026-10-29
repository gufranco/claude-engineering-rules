# Documentation Truth

## Core Rule

Documentation that describes code is a claim about the code. A change that makes a claim false must correct it in the same change. A document left behind after the code moved does not become merely outdated; it becomes a statement that is wrong, and it is trusted precisely because it is written down.

The scope is every artifact that asserts something about code: README files, API documentation, OpenAPI and AsyncAPI specifications, `.env.example`, architecture documents, runbooks, and pull request descriptions.

## Why This Rule Exists

A prose rule such as "update everything the change affects" in [`code-style.md`](../rules/code-style.md), and a [`documentation-checker`](../agents/documentation-checker.md) agent, do not stop documentation from drifting. The reason is timing, not wording. Enforcement layers fire at different moments relative to the work:

| Layer | Fires | Can it change what gets written? |
|---|---|---|
| Always-on rule | Before the work | Yes |
| On-demand standard | Only on a trigger match | Sometimes |
| Review checklist | After the artifact exists | Only by asking for a rewrite |
| Reviewer agent | After the artifact exists | Only by asking for a rewrite |
| Write-time hook | At the moment of publishing | Yes, mechanically |

More prose at the first layer does not help, because the layer that matters is the one that fires when the change is published. [`doc-sync-guard.py`](../hooks/doc-sync-guard.py) is that layer.

## Obligations

### A name that disappears from code disappears from the documentation

When an exported symbol, a command-line flag, a package script, an environment variable, a route, or a database column is removed or renamed, every document that names it must change in the same commit. This is the obligation the hook enforces, because it is the one that is mechanically certain: the document asserts a thing exists, and the thing does not exist.

### A new environment variable is documented before it is read

`.env.example` is a complete list by definition, so a variable the code reads and the example file does not name is a defect the moment it is introduced. This is the one addition the hook enforces, for the same reason: completeness makes the absence certain.

### Documentation for additions is the author's obligation, not the hook's

A new flag, a new script, or a new endpoint must be documented wherever its peers are documented. The hook does not enforce this, because a README that documents three of five flags is a style choice the tool cannot distinguish from an omission. A check that cannot be stated without a maybe stays out of the hook and stays in review.

### A pull request description is documentation

It describes the change to the people deciding whether to accept it. When the code moves after the description is written, the description must move with it. [`/morning`](../skills/morning/SKILL.md) detects the drift across open pull requests and [`/pr-summary`](../skills/pr-summary/SKILL.md) drafts the correction.

### A volatile section carries a date

The hook catches a document that became false. It cannot catch a document that merely became old, and the two fail differently. A falsified claim is wrong now; an aged claim was true once and nobody can tell when.

Any section describing current state rather than durable structure carries a date in its heading.

```markdown
## Known issues (as of 2026-08-26)

## Current provider limits (as of 2026-08-26)
```

The stamp costs nothing and does two things: a reader sees the age without opening the history, and an agent knows to re-verify before asserting any of it. This is the freshness trichotomy from [`knowledge-notes.md`](../rules/knowledge-notes.md) applied to repository documentation. A present-tense claim about something that moves, sitting outside a dated container with no stamp, reads as true forever.

### Name the documents and the condition that triggers each

"Update the docs" is unactionable, so it is ignored. A table naming each document and the change that obliges an update is not.

```markdown
When opening a pull request, check whether the change affects these and update:

| Document | Update when |
|---|---|
| the instruction file | tech stack, schema, endpoints, commands, or key patterns changed |
| `docs/architecture.md` | structure, schema, or the build pipeline changed |
| the README | setup, prerequisites, env vars, or user-facing features changed |
```

Where a document changes often, state a materiality boundary in the same row, so the obligation stays credible rather than becoming a formality: new inputs, new deploy paths, or changed approval behavior count; a version pin bump or a trivial refactor does not. The full authoring guidance is in [`agent-instruction-files.md`](agent-instruction-files.md).

### A stale description loses to the code

The obligations above prevent drift in the change that causes it. This one covers drift that already happened: a project instruction file or README describes a convention, and the code consistently does something else. Follow the code, and list every mismatch found between the document and the code in the final reply, naming the document line and the code that contradicts it, so the document gets corrected.

The reason is measured. Xu and Wu, "Stale Instruction Files Override the Code in Coding Agents: A One-Sentence Fix", arXiv 2610.30571, built 40 Python projects whose instruction file asked for one convention while the code used another, and ran Claude Code and Codex CLI 320 times. Without a precedence sentence the agents followed the stale file in 90.1% of choices; Claude Code noticed the conflict in 79 of 80 runs and followed the file anyway, and Codex CLI rewrote working code to match the file in 20 of 80 runs, failing the project's tests in 17. With one user-level sentence giving existing code precedence, choices following the code rose from 4.2% to 91.4% and the test pass rate from 89.4% to 100%. The authors attribute the bias to the file arriving as an instruction while the code arrives as tool output.

Three limits keep this narrow:

- It applies to descriptions, never to rules. "API fields are `snake_case`" is a description the code can falsify. "Never use `any`" is a rule, and existing violations are not precedent, per the priority order in [`../CLAUDE.md`](../CLAUDE.md).
- "Consistently" means the code agrees with itself. When the code is split between both conventions, the document wins and the split is reported.
- A document that marks a path as mid-migration to the convention it describes keeps precedence for that path; otherwise the agent faithfully copies the legacy code it is meant to replace.

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

- [`code-style.md`](../rules/code-style.md) Completeness: the general obligation this rule sharpens for documentation.
- [`found-fix.md`](../rules/found-fix.md): a stale document surfaced by any verification surface is in scope for the current change.
- [`markdown-links.md`](../rules/markdown-links.md): the companion rule for references that point at files rather than at symbols.
- [`../standards/documentation.md`](documentation.md): preserve existing valid information when a skill rewrites a document. Merge, never replace.
- [`../agents/documentation-checker.md`](../agents/documentation-checker.md): the post-hoc reviewer this rule complements rather than replaces.

## Enforcement

Enforced by: [`hooks/doc-sync-guard.py`](../hooks/doc-sync-guard.py).

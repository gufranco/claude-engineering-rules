# Agent Instruction Files

How to author the instruction file a repository hands to a coding agent. Loaded on demand when creating or revising a harness instruction file, `AGENTS.md`, `.cursorrules`, `copilot-instructions.md`, or the Claude Code equivalent, and when a project needs agent-facing configuration such as launch or session setup.

This standard covers the file a **project** ships. The personal configuration in `~/.claude/` is governed by [the global instructions](../CLAUDE.md) and the rules beside them.

## The Governing Constraint

The file is injected into every prompt for every session in that repository, forever. That makes it the most expensive text in the project per byte, and it inverts the usual documentation instinct.

A README describes the project. An instruction file **corrects the agent's defaults**. Those are different documents, and writing the first one when the second is needed is the most common failure.

The admission test for every line: **would a competent agent get this wrong, or waste turns, without it?**

- It would work this out from the code in a turn or two. Cut it.
- It is standard behavior of a well-known framework. Cut it.
- It restates the directory tree, which the agent can list. Cut it.
- It is true, important, and the agent would confidently assume the opposite. Keep it.

A thirty-line file that corrects five wrong assumptions beats a four-hundred-line file that describes the repository accurately.

## Harness-Agnostic Layout

Tools read different filenames. Maintaining the same content in several is guaranteed drift. Two working approaches:

**Canonical file plus symlinks.** One real file, the rest are symlinks pointing at it. Simplest, and it survives tools that do not support imports. It fails when two harnesses need genuinely different content.

**Modular directory plus thin adapters.** One directory holds the content; each harness gets a small file that imports what it needs.

```
.ai/
  context.md
  core-rules.md
  pre-flight.md
  post-review.md
<harness file>                     imports the set
.github/copilot-instructions.md    imports the set
.cursor/rules/rules.mdc            imports the set
```

Costs more structure and buys per-harness selection plus per-topic files that can be revised independently. Worth it once the content exceeds roughly two hundred lines or a second harness needs a different subset.

Pick one per repository and say which in the file. Two repositories in the same organization independently solving this and never comparing notes is the normal outcome; write down which one this repository chose.

## Progressive Disclosure

Split the moment the file exceeds what anyone reads in one pass. A working three-way split:

| File | Holds | Read |
|---|---|---|
| The instruction file | Overview, corrected defaults, stop list, pointers | Always, every session |
| An architecture file | Structure, schema, boundaries, build pipeline | When touching structure |
| A patterns file | How to add a route, a table, a component | When adding something of that kind |

The instruction file names the other two and states the condition for reading each. It never inlines them.

## Correct the Default, Then Stop

The highest-value paragraph in any instruction file is the one that closes off a wrong assumption the agent will otherwise act on with total confidence.

> Merging to `main` **is** the deploy. There is no separate apply step, and a local
> apply races the pipeline for the state lock. Do not tell anyone to run it manually.

> Every request reaching this app is already authenticated by a proxy. There is no
> logged-out state and no unauthenticated visitor. Do not build a login page, do not
> add an auth library, delete any you find.

> The environment variables in the infrastructure code are **not applied** to the
> running services. They are documentation. Rollout is manual.

Each closes a whole category of plausible, confident, wrong work. The second is the strongest form: a section written entirely as prohibitions, because naming the invariant makes the prohibitions obvious rather than arbitrary.

Write a **"what you do not need to build"** section wherever the platform already provides something the agent would otherwise construct.

## The Stop List

A short, explicit list of conditions where the correct action is to stop and ask rather than proceed. Four to six items.

```markdown
## When to stop and ask

- The request needs a change to the platform itself, new infrastructure, a new
  auth model, or cross-app data sharing with custom rules.
- The request needs a runtime this platform does not support.
- The request implies per-user permissions. There is no authorization layer here;
  it would have to be built in the app.
- The request references a file or config not covered here. Check the technical
  docs, otherwise ask.
```

Name a human for categories the agent should never attempt. "Pipeline and deploy failures go to the platform owner" is more useful than any amount of debugging guidance for a system the agent cannot see.

A per-project stop list is more reliable than a general confidence heuristic, because it names the specific things this project makes look easier than they are.

## Exemplar and Anti-Exemplar

Two lines beat two pages.

```markdown
- Follow this structure: `lib/components/cities/`, `lib/components/drops/`
- Avoid these patterns: `lib/blocs/redeem/`
```

A worked example already in the repository carries every convention at once, including the ones nobody wrote down. The anti-exemplar is the half usually omitted and is often the more useful: it tells the agent that code it will encounter, and might reasonably imitate, is not the standard.

Keep both current. An exemplar that has drifted teaches the drift.

## Escape Valves On Thresholds

A numeric threshold with no valve produces either compliance or silent violation. Name the exceptions and the deciding question.

```markdown
Target: under 300 lines.

Acceptable above it for: state machines with interlocking cases, generated code,
a single calculation engine, a service whose operations genuinely share state.

Deciding question: if splitting makes the code harder to understand, keep it
together and record why.
```

The same shape works for any "when does this abstraction earn its place" judgment: a create-when list beside a skip-when list, with the deciding question at the end.

## Anti-Read Directives

An instruction file can spend context as easily as save it. Where the repository contains a large reference set, say plainly that it must not be read in bulk, state the size so the cost is legible, and route to the one file that answers each kind of question.

```markdown
Do not read the API reference in bulk. 50 files, 182 endpoints. Consult it only
for the specific detail needed now, and read only that endpoint's file.

| Task | Read |
|---|---|
| Quick technique lookup | `reference/quick-reference.md` only |
| Design validation | `reference/common-mistakes.md`, then the quick reference |
| Topic deep dive | `reference/index.md` to find the chapter, then that chapter only |
```

A routing table is the difference between a reference library that helps and one that consumes the context window before work starts.

## Preemptive Error Fingerprints

When a failure has a distinctive message and a non-obvious cause, put the literal message in the file next to the fix. Recognition is instant; diagnosis from first principles is not.

```markdown
Changing the manifest without regenerating the lockfile passes locally and fails
the deploy build with:

    npm error `npm ci` can only install packages when your package.json and
    npm error package-lock.json are in sync.

Run the install and commit both files together.
```

The same applies to failures that produce a *misleading* message. A push rejected as a non-fast-forward can surface as an HTTP 403, which reads as a permissions problem and sends the reader diagnosing the wrong system entirely. Write down the real cause beside the message that hides it.

## Inference Tables

When the tooling infers behavior from file presence, state the inference as a table. Anything the agent would otherwise have to derive by reading build scripts belongs here.

```markdown
| Present in the folder | Runtime |
|---|---|
| `Dockerfile` | custom container |
| `next.config.*` | framework server |
| anything else | static |
```

Then state the consequence of getting it wrong, which is the part that makes the table actionable: adding a `Dockerfile` to a static app silently promotes it to its own service at higher cost.

## Machine-Owned Fields

Anything a pipeline writes must be marked as off limits, with the reason.

```markdown
Do not edit the `version` field. A workflow bumps it on every merge. A manual
edit conflicts with the bot's commit and wastes a pipeline run.
```

Without this, an agent tidying a manifest will helpfully bump a version and create a conflict nobody expected.

## Documentation Maintenance Routing

"Keep the docs updated" is ignorable. A table of documents with the condition that triggers each one is not.

```markdown
When opening a pull request, check whether the change affects these and update:

| Document | Update when |
|---|---|
| this file | tech stack, schema, endpoints, commands, or key patterns changed |
| `docs/architecture.md` | structure, schema, or build pipeline changed |
| `docs/patterns.md` | conventions or domain logic changed |
| the README | setup, prerequisites, env vars, or user-facing features changed |
```

State a materiality boundary for anything that changes often, so the obligation stays credible: new inputs, new deploy paths, or changed approval behavior count; a version pin bump or a trivial refactor does not.

## Dated Staleness Stamps

Any section describing current state rather than durable structure carries a date in its heading.

```markdown
## Known issues (as of 2026-08-26)
```

A reader sees the age without checking history, and an agent knows to re-verify before asserting. This is the freshness policy from [`knowledge-notes.md`](../rules/knowledge-notes.md) applied to a repository file: a present-tense claim about something that moves, with no stamp, reads as true forever.

## Session Rituals

For repositories carrying long multi-session initiatives, a fixed read order and a fixed close-out are worth more than any amount of prose.

```markdown
## Session start

1. Read the plan, then the status file, then the decision log, in that order.
2. State your understanding in one sentence before starting.
3. Check `git log` and `git status` rather than trusting what any document
   claims about working-tree state.

## Session end

1. Update the status file: done, in flight, blocked, next.
2. Append any non-trivial decision to the decision log.
3. Surface anything blocking at the top of the final message, not only in a file.
```

Two supporting files:

| File | Shape |
|---|---|
| Status | Living handoff. Newest state at top. Rewritten every session |
| Decisions | Append-only log. One dated entry per non-trivial choice: decision, rationale, alternatives, links. Never deleted, superseded entries marked |

Step 3 of the start ritual is the one that pays for itself. A document describing working-tree state is a claim about the past, and the agent that trusts it starts by rebuilding something that already exists.

### Pivot cascade

When a decision changes mid-initiative, the **same session** updates every document the change invalidates: the cross-initiative decision table, every affected plan, and a new entry in the decision log. Stale plans silently break the next session, and the cost lands on someone who was not there for the decision.

## Intent Routing

An agent should not require the operator to know a command name. Where a repository or configuration provides commands, map the phrasings people actually use.

```markdown
When a request matches one of these, invoke the command instead of improvising:
a raw idea to file -> /capture; "what changed lately" -> /brief; "this looks
wrong" -> /falsify; "bring things up to date" -> /sync.
```

The underlying reason is worth stating outright, because it explains why the table is needed at all: **skills and commands do not self-invoke reliably from their descriptions alone.** Where invocation matters, hard-code it with a precise trigger boundary naming what counts and what does not.

## Agent-Facing Configuration

Two files remove work that would otherwise be inferred every session.

**Launch configuration** at `.claude/launch.json` declares how to start the app, so nothing has to be reconstructed from build scripts.

```json
{
  "version": "0.0.1",
  "configurations": [
    { "name": "dev", "runtimeExecutable": "pnpm", "runtimeArgs": ["run", "dev"], "port": 5173 }
  ]
}
```

**Session setup hook** in the project settings ensures a session never opens against a repository that cannot build.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [{ "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/install-deps.sh" }]
      }
    ]
  }
}
```

Both are per-project and belong in the repository. Keep the hook fast and idempotent; a slow session-start hook is a tax on every resume, per [`agent-operating-limits.md`](../rules/agent-operating-limits.md).

## Contributor Directory

A name-to-handle table costs a few lines and removes a whole class of guesswork for reviewer assignment, commit attribution lookups, and issue routing. Worth including in repositories with a stable set of contributors.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| Describing the repository rather than correcting the agent's defaults | Pays a per-session cost for information the agent already has |
| Restating the directory tree | The agent can list directories |
| Documenting standard framework behavior | Known, and it goes stale on the next major version |
| "Keep the documentation updated" with no document list and no condition | Unactionable, therefore ignored |
| A present-tense claim about volatile state with no date | Reads as true forever |
| The same content maintained in several harness files | Guaranteed to drift; use a symlink or an import |
| A large reference set with no routing table and no anti-read directive | Consumes the context window before work begins |
| An exemplar that has drifted from current practice | Teaches the drift with full authority |
| A numeric threshold with no named exceptions | Produces silent violation rather than compliance |
| Omitting that a field is written by a pipeline | An agent tidying the file creates a conflict |
| A stop list that names no human for what the agent must not attempt | Leaves the agent to improvise on the systems it cannot see |

## Cross-References

- [`agent-operating-limits.md`](../rules/agent-operating-limits.md): context cost, anti-read economics, unconditional injection tax.
- [`doc-truth.md`](../rules/doc-truth.md): documentation as a claim about code, and the obligation when a change falsifies it.
- [`knowledge-notes.md`](../rules/knowledge-notes.md): the freshness trichotomy that dated stamps implement.
- [`living-specs.md`](../rules/living-specs.md): the living behavioral spec that session rituals feed.
- [`project-glossary.md`](../rules/project-glossary.md): the per-project vocabulary an instruction file should use rather than redefine.
- [`documentation.md`](documentation.md): preserving existing valid content when revising a document.

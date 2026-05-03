---
name: memory-supersede
description: Supersede-not-delete chain for project and feedback memories. Reference memories may still be deleted when stale.
---

# Memory Supersede

## Core Rule

When updating a memory, do not silently overwrite it. The previous version may still be useful as historical context. Project and feedback memories support a supersede chain. Reference memories may be deleted outright when stale.

## When to Apply

| Memory type | Update behavior |
|------------|----------------|
| `project` | Supersede-not-delete. The new memory file references the old one via `superseded_by` frontmatter |
| `feedback` | Supersede-not-delete. Same chain pattern as project memories |
| `reference` | Delete and replace. References point to external resources; stale references mislead |
| `user` | Update in place when correcting a fact about the user. Supersede when the user's role or focus genuinely changed |

## Supersede Format

When a project or feedback memory needs replacement:

1. Keep the original file. Add a `superseded_by: <new-file.md>` line to its frontmatter.
2. Write the new memory in a new file with a fresh name.
3. Add a `supersedes: <old-file.md>` line to the new memory's frontmatter.
4. Update `MEMORY.md` to point to the new file. Remove the old file's index entry only if the old context is no longer load-bearing.

```markdown
---
name: feedback example
description: short hook
type: feedback
superseded_by: feedback_example_v2.md
---

<original content unchanged>
```

```markdown
---
name: feedback example v2
description: refined version
type: feedback
supersedes: feedback_example.md
---

<new content>
```

## Chain Limits

- Maximum chain depth: 5 supersessions. Beyond this, archive the oldest entries to a `memory/archive/` directory and remove from the chain.
- The supersede chain must form a directed acyclic graph. Never point two new memories at the same predecessor unless one is genuinely a fork (rare).

## Why This Rule Exists

Overwriting memories destroys the trail of how the user's preferences evolved. A project memory that says "we use Postgres" overwritten by "we use MySQL" leaves no record of the transition. Knowing both helps the assistant infer what tooling, code, and integrations may still reflect the older choice.

Reference memories are exempt because they point to external resources that change. A stale URL is worse than no URL.

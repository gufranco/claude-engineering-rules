---
name: memory-supersede
description: Supersede-not-delete chain for project and feedback memories. Reference memories may still be deleted when stale.
---

# Memory Supersede

Never silently overwrite a memory; the prior version is history.

- `project` and `feedback`: keep the old file with `superseded_by:`, write a new one with `supersedes:`, repoint the index.
- `reference`: delete and replace. `user`: update in place unless the role genuinely changed.
- Max chain depth 5. With a vault configured, the chain lives in the note's `timeline:`.

Full rule, examples, and rationale: [`standards/memory-supersede.md`](../standards/memory-supersede.md). Read it before updating any memory.

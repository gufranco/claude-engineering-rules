---
name: learn
description: Manage operational learnings across sessions. Subcommands: show, search, add, prune, export, stats. Stores insights with confidence scoring and decay so the most relevant learnings surface first. Use when user says "learn", "save this insight", "what did we learn", "search learnings", "show learnings", or wants to persist knowledge across sessions. Do NOT use for checkpoints (use /checkpoint), retrospectives (use /retro), or documentation updates (use /readme).
---

Persistent knowledge base for patterns, corrections, and observations discovered during work. Learnings survive across sessions and decay in relevance over time.

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/learn` or `/learn show` | Show the 10 most recent learnings, sorted by confidence |
| `/learn search <keyword>` | Search learnings by keyword match against key and insight fields |
| `/learn add <insight>` | Add a new learning interactively |
| `/learn prune` | Remove entries with confidence below 2 |
| `/learn export` | Export all learnings to a markdown file |
| `/learn stats` | Show analytics: total count, type distribution, average confidence |

## Storage

Learnings are stored in `~/.claude/telemetry/learnings.jsonl` as one JSON object per line.

Each entry has this schema:

```json
{
  "id": "learn-20260404-120000",
  "type": "observed",
  "key": "prisma-migration-ordering",
  "insight": "Prisma migrations must have the latest timestamp to avoid ordering conflicts after rebase.",
  "confidence": 8,
  "source": "rules/git-workflow.md",
  "timestamp": "2026-04-04T12:00:00Z",
  "lastAccessed": "2026-04-04T12:00:00Z"
}
```

| Field | Description |
|-------|------------|
| `id` | Unique identifier: `learn-YYYYMMDD-HHmmss` |
| `type` | One of: `observed` (seen in code/logs), `inferred` (deduced from patterns), `corrected` (user corrected a wrong assumption) |
| `key` | Short kebab-case label for the learning, 2-5 words |
| `insight` | The learning itself, one to three sentences |
| `confidence` | Integer 1-10. Higher means more certain and more frequently validated |
| `source` | File path, session ID, or "user" indicating where the learning originated |
| `timestamp` | GMT timestamp of when the learning was created |
| `lastAccessed` | GMT timestamp of when the learning was last read or confirmed |

## Process

### Show

1. Read `~/.claude/telemetry/learnings.jsonl`.
2. Apply confidence decay: for each entry with type `inferred`, subtract 1 point per 30 days since `lastAccessed`. Do not modify the file during show, only adjust the display score.
3. Sort by adjusted confidence descending.
4. Display the top 10 as a table:

   | Key | Type | Confidence | Insight |
   |-----|------|-----------|---------|

### Search

1. Read all entries from the JSONL file.
2. Filter entries where `key` or `insight` contains the search keyword, case-insensitive.
3. Sort by confidence descending.
4. Display matching entries as a table. If no matches, state "No learnings match that keyword."

### Add

1. Ask the user for the learning if only `/learn add` was given without inline text.
2. Classify the type:
   - `observed`: the user saw this happen.
   - `inferred`: derived from patterns, not directly witnessed.
   - `corrected`: the user is correcting a previous assumption.
3. Generate a kebab-case key from the insight.
4. Set initial confidence: 8 for `observed`, 6 for `inferred`, 9 for `corrected`.
5. Ask the user to confirm or adjust the key, type, and confidence.
6. Append the entry to the JSONL file.
7. Create the `~/.claude/telemetry/` directory if it does not exist.

### Prune

1. Read all entries.
2. Apply confidence decay to `inferred` entries.
3. Identify entries with adjusted confidence below 2.
4. Show the entries that will be removed and ask for confirmation.
5. Rewrite the file without the pruned entries.
6. State how many entries were removed.

### Export

1. Read all entries.
2. Group by type.
3. Write to `~/.claude/telemetry/learnings-export.md` with this structure:

   ```markdown
   # Learnings Export

   **Exported:** <GMT timestamp>
   **Total entries:** <count>

   ## Observed

   - **<key>** (confidence: N): <insight>

   ## Inferred

   - **<key>** (confidence: N): <insight>

   ## Corrected

   - **<key>** (confidence: N): <insight>
   ```

4. State the export file path.

### Stats

1. Read all entries.
2. Compute:
   - Total count.
   - Count by type.
   - Average confidence by type.
   - Oldest and newest entry timestamps.
   - Number of entries with decayed confidence below 5.
3. Display as a summary table.

## Confidence Decay

Inferred learnings lose relevance over time if not accessed or confirmed.

- Decay rate: 1 point per 30 days since `lastAccessed`.
- Minimum: 1. Confidence never drops below 1 from decay alone.
- Decay applies only to `inferred` type. `observed` and `corrected` do not decay.
- When a learning is accessed via `show` or `search`, update its `lastAccessed` timestamp in the file to reset the decay clock.

## Rules

- The JSONL file is append-only during normal operations. Only `prune` rewrites it.
- All timestamps in GMT.
- Never auto-add learnings without user involvement. The user decides what is worth persisting.
- Duplicate detection: before adding, check if a learning with the same key already exists. If it does, ask whether to update the existing entry or create a new one.
- Create the `~/.claude/telemetry/` directory if it does not exist.

## Related Skills

- `/retro` -- Session retrospective that may generate learnings.
- `/checkpoint` -- Save session state, complementary to learnings.
- `/review` -- Code review may surface learnings about project patterns.

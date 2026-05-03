---
name: maintenance
description: Inspect ~/.claude config for staleness without mutating. Reports orphan skills, unused hooks, stale memories, broken index references, and oversized files. Read-only by default. Mutations require --apply and per-item confirmation. Use when user says "maintenance", "tidy up claude config", "audit my claude setup", "find stale config", "report orphans", or wants a hygiene pass on personal config. Do NOT use for repo-level cleanup (use /cleanup), code refactor (use /refactor), or session retrospective (use /retro).
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
mode: read-only
sensitive: true
---

Health check for `$HOME/.claude`. Report by default. Archive, never delete. Apply changes only with explicit approval per item.

## Arguments

- No arguments: produce a report. No mutations.
- `--apply`: enter interactive mutation mode. Each finding is presented and must be confirmed individually.
- `--archive-dir <path>`: where archived files go. Default `$HOME/.claude/archive/<YYYY-MM-DD>/`.

## Process

### 1. Inventory

In parallel, enumerate:

| Set | Path |
|-----|------|
| Skills | `$HOME/.claude/skills/*/SKILL.md` |
| Rules | `$HOME/.claude/rules/*.md` and `$HOME/.claude/rules/lang/*.md` |
| Standards | `$HOME/.claude/standards/*.md` |
| Hooks | `$HOME/.claude/hooks/*.py`, `*.sh` |
| Memories | `$HOME/.claude/projects/-Users-*-claude/memory/*.md` |
| Specs | `$HOME/.claude/specs/*/` |

Also read:
- `$HOME/.claude/rules/index.yml`
- `$HOME/.claude/README.md`
- `$HOME/.claude/settings.json`
- Memory `MEMORY.md` index files.

### 2. Findings by category

**Orphan skills.** A skill file exists but is not mentioned in `README.md` or referenced by any other skill, rule, or standard.

**Orphan rules and standards.** A file exists in `rules/` or `standards/` but is not registered in `rules/index.yml` and not referenced from any other rule or standard.

**Broken index references.** `rules/index.yml` mentions a path that does not exist on disk.

**Hook drift.** A hook file is not registered in `settings.json`, or `settings.json` references a hook file that does not exist.

**Stale memories.**
- A memory whose `superseded_by` target does not exist.
- A memory chain longer than 5 entries (apply `rules/memory-supersede.md`).
- A memory file not listed in its `MEMORY.md` index.
- A memory in `MEMORY.md` whose file does not exist.

**Oversized files.** Any rule, standard, or skill larger than 500 lines. Surface for review per `rules/code-style.md` file size guidance.

**Stale specs.** Spec folders older than 90 days with no recent activity.

### 3. Report

Produce a single report. No edits. Format:

```markdown
# Maintenance report

Generated: <YYYY-MM-DD HH:MM GMT>

## Summary
- Orphan skills: N
- Orphan rules/standards: N
- Broken index references: N
- Hook drift: N
- Stale memories: N
- Oversized files: N
- Stale specs: N

## Orphan skills
| Path | Last touched | Reason |
|------|--------------|--------|
| ... | ... | not in README, not referenced |

## Orphan rules and standards
| Path | Reason |
|------|--------|
| ... | not in index.yml, no inbound references |

## Broken index references
| Index path | Disk path | Status |
|-----------|-----------|--------|
| ... | ... | missing |

## Hook drift
| Hook file | settings.json | Status |
|-----------|---------------|--------|
| ... | ... | unregistered / missing on disk |

## Stale memories
| File | Issue |
|------|-------|
| ... | superseded_by points to missing file |
| ... | chain depth 6, exceeds limit |

## Oversized files
| File | Lines | Suggestion |
|------|-------|-----------|
| ... | 612 | extract sections |

## Stale specs
| Folder | Age | Last touched |
|--------|-----|--------------|
| ... | 117 days | <date> |
```

### 4. Apply (only with `--apply`)

For each finding, present a single proposed action and ask for confirmation. Never batch.

| Finding | Proposed action |
|---------|----------------|
| Orphan skill | Move to `archive/<date>/skills/<name>/` |
| Orphan rule or standard | Move to `archive/<date>/<dir>/<name>.md` |
| Broken index reference | Remove the entry from `rules/index.yml` |
| Hook drift (unregistered) | Add stub to `settings.json` or move file to archive |
| Hook drift (missing) | Remove entry from `settings.json` |
| Stale memory (broken chain) | Move to `archive/<date>/memory/`, drop from `MEMORY.md` |
| Oversized file | Surface for manual extraction. Never auto-split |
| Stale spec | Move to `specs/archive/<date>/<slug>/` |

After every accepted action:
1. Show the diff or move command.
2. Apply.
3. Update the corresponding index file (`README.md`, `rules/index.yml`, `MEMORY.md`).
4. Commit with conventional format. Each accepted action is its own commit.

## Rules

- Default mode is read-only. The report alone is the deliverable unless `--apply` is passed.
- Never delete. Always archive. The user can purge `archive/` manually.
- Never mutate without per-item confirmation, even with `--apply`.
- Apply `rules/memory-supersede.md` for memory chain handling.
- Apply `rules/git-workflow.md` Local Quality Gate before committing any change.
- Never touch project-level config. This skill operates on `$HOME/.claude` only.
- The report cites every finding with a path. No abstract claims.

## Related skills

- `/cleanup` for repository-level branch and PR hygiene.
- `/retro` for session learnings, not config audit.
- `/health` for project code quality, not personal config.

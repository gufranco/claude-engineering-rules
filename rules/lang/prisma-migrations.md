# Prisma Migrations

## Core Rule

`schema.prisma` is the single source of truth. Every DDL statement in a migration file must have a matching declaration in `schema.prisma`. Migrations and schema are two views of the same state; if they disagree, every developer who runs `prisma migrate dev` on a fresh DB gets a phantom drift migration.

## Parity Requirements

| Migration SQL | Required in `schema.prisma` |
|---------------|------------------------------|
| `CREATE INDEX <name> ON "<Model>" (...)` | `@@index([cols], map: "<name>")` on the model |
| `CREATE UNIQUE INDEX <name> ON "<Model>" (...)` | `@@unique([cols], map: "<name>")` on the model |
| `ALTER TABLE "<Model>" ADD COLUMN "<col>"` | Field on the model |
| `ALTER TABLE "<Model>" DROP COLUMN "<col>"` | Field removed from the model |
| `DROP INDEX <name>` | `@@index` removed from the model |
| `CREATE TABLE "<Model>"` | `model <Model>` block |
| `DROP TABLE "<Model>"` | `model <Model>` block removed |

## Index Naming Convention

Always pass `map:` explicitly. Default Prisma names collide with raw-SQL names and cause drift.

```prisma
@@index([homeTeam], map: "Game_homeTeam_sportsbook_search_idx")
```

Pattern: `<Model>_<col>(_<col>)*_<purpose>_idx`. Example purposes: `lookup`, `search`, `sort`, `fk`.

## Unmanaged Objects

Some PostgreSQL objects cannot be expressed in Prisma:

- Extensions (`pg_trgm`, `uuid-ossp`)
- Custom triggers and functions
- Materialized views
- Partial / expression indexes with operator classes (`gin_trgm_ops`)
- Row-level security policies

For these, the migration SQL has no schema-side counterpart. Set the `PRISMA_SCHEMA_SYNC_DISABLE=1` env var for that single tool call and note the bypass reason in the migration's leading comment.

## Verification (MANDATORY)

Before opening any PR that touches a migration:

```bash
# 1. Static parity check (offline)
pnpm exec prisma format --schema packages/database/prisma/schema.prisma

# 2. Authoritative drift check (requires DB)
pnpm exec prisma migrate diff \
  --from-schema-datamodel packages/database/prisma/schema.prisma \
  --to-migrations packages/database/prisma/migrations \
  --exit-code
```

`migrate diff --exit-code` returns 0 when schema and migrations agree. Non-zero exit is a blocking issue.

## End-to-End Verification

When the change is non-trivial (new index, new column, new model):

1. Spin up a fresh DB (`docker-compose -f docker-compose.test.yml up -d`).
2. Run all migrations: `prisma migrate deploy`.
3. Run `prisma migrate dev` with no name. If Prisma generates a new migration, the schema and migrations are out of sync. Investigate and fix before pushing.

## Originating Incident

**PR #1325 (onyxodds/onyx_fullstack), merged 2026-04-17.**

Migration `20260413180000_sportsbook_search_trgm_indexes` added 7 `CREATE INDEX IF NOT EXISTS` statements without `@@index` entries in `schema.prisma`:

- `Game_homeTeam_sportsbook_search_idx`
- `Game_awayTeam_sportsbook_search_idx`
- `Game_league_sportsbook_search_idx`
- `Game_sport_sportsbook_search_idx`
- `Line_name_sportsbook_search_idx`
- `Line_marketName_sportsbook_search_idx`
- `Line_selection_sportsbook_search_idx`

Detection lag: 17 days. Detected only when a developer ran migrations on a clean local DB and Prisma generated a phantom drift migration trying to remove the seven indexes.

Fix: PR #1559 added the seven `@@index` entries with explicit `map:` names and ran `prisma migrate diff --exit-code` to confirm zero drift.

## Cross-References

- `~/.claude/rules/code-style.md` "Prisma Schema Completeness" covers required fields and indexes per model.
- `~/.claude/rules/git-workflow.md` "Migration Ordering" and "Migration Idempotency" cover timestamp ordering and `IF NOT EXISTS` requirements.
- `~/.claude/rules/verification.md` "Database changes add" lists the verification gates.
- `~/.claude/checklists/checklist.md` category "Schema-Migration Sync" is the per-PR checklist.

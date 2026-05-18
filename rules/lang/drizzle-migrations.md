# Drizzle Migrations

## Core Rule

The TypeScript schema files under `src/db/schema/` are the single source of truth. Every column, index, unique constraint, foreign key, and check constraint declared in TypeScript must have a matching DDL statement in the SQL files under `drizzle/` (or the configured `out` directory). The SQL files must, in turn, never include DDL that has no TypeScript counterpart. Code and migrations are two views of the same state. When they disagree, `drizzle-kit generate` will produce a phantom migration the next time anyone touches the schema.

## Schema Sync Strategy (MANDATORY)

Drizzle ships two distinct workflows. They are not interchangeable, and one of them must never reach production.

| Command | Effect | Use in |
|---------|--------|--------|
| `drizzle-kit generate` | Reads the TypeScript schema, diffs against `drizzle/_meta/_journal.json`, writes a new SQL migration file and updates the journal | Every environment |
| `drizzle-kit migrate` | Reads the SQL files and applies any that are not yet in `__drizzle_migrations` | Every environment |
| `drizzle-kit push` | Reads the TypeScript schema, diffs against the live database, executes the DDL directly without writing a file | Local development only |
| `drizzle-kit pull` | Reads the live database, writes a TypeScript schema and a baseline migration | Onboarding to an existing database, never in steady state |

`drizzle-kit push` bypasses the migration file system entirely. It can silently skip changes that Drizzle considers ambiguous (column renames, type narrowing), and it leaves no SQL record of what ran. A staging or production environment that has ever been `push`ed against has no reliable migration history. Never run `drizzle-kit push` against staging or production. Configure CI to fail when `push` appears in a deployment script.

The recommended workflow:

1. Local development: `drizzle-kit push` for fast iteration during prototyping. Switch to `generate` + `migrate` as soon as the schema stabilizes.
2. Pre-release: `drizzle-kit generate` to capture the schema delta as a versioned SQL file. Commit both the file and the updated `_meta/_journal.json`.
3. Deployment: `drizzle-kit migrate` runs against staging and production as a deployment step before the application boots.

## Parity Requirements

| Migration SQL | Required in TypeScript schema |
|---------------|------------------------------|
| `CREATE INDEX <name> ON "<table>" (...)` | `index('<name>').on(table.col)` in the table's index callback |
| `CREATE UNIQUE INDEX <name> ON "<table>" (...)` | `uniqueIndex('<name>').on(table.col)` |
| `ALTER TABLE "<table>" ADD COLUMN "<col>"` | Column in the `pgTable`/`mysqlTable`/`sqliteTable` definition |
| `ALTER TABLE "<table>" DROP COLUMN "<col>"` | Column removed from the table definition |
| `DROP INDEX <name>` | `index` or `uniqueIndex` removed from the index callback |
| `CREATE TABLE "<table>"` | `pgTable('<table>', ...)` export |
| `DROP TABLE "<table>"` | Export removed |
| `ALTER TABLE ... ADD CONSTRAINT "<fk>" FOREIGN KEY ...` | `.references(() => other.id)` on the column |
| `ALTER TABLE ... ADD CONSTRAINT "<chk>" CHECK ...` | `check('<name>', sql`<expression>`)` in the third argument |

## Index Naming Convention

Always pass an explicit name as the first argument to `index()` and `uniqueIndex()`. Drizzle does not auto-generate index names. Without an explicit name, the index is anonymous in SQL and cannot be referenced from later migrations.

```typescript
import { pgTable, text, timestamp, uuid, index, uniqueIndex } from 'drizzle-orm/pg-core';

export const game = pgTable(
  'game',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    companyId: uuid('company_id').notNull(),
    homeTeam: text('home_team').notNull(),
    status: text('status').notNull(),
    createdAt: timestamp('created_at').notNull().defaultNow(),
    updatedAt: timestamp('updated_at').notNull().defaultNow().$onUpdateFn(() => new Date()),
  },
  (table) => ({
    homeTeamSearchIdx: index('Game_homeTeam_sportsbook_search_idx').on(table.homeTeam),
    companyStatusIdx: index('Game_companyId_status_idx').on(table.companyId, table.status),
    companyCreatedIdx: index('Game_companyId_createdAt_idx').on(table.companyId, table.createdAt),
  }),
);
```

Pattern: `<Table>_<col>(_<col>)*_<purpose>_idx`. Purposes: `lookup`, `search`, `sort`, `fk`, `partial`.

## Unmanaged Objects

Some PostgreSQL and MySQL objects cannot be expressed in Drizzle column definitions:

- Extensions (`pg_trgm`, `uuid-ossp`, `pgcrypto`)
- Custom triggers and functions
- Materialized views (Drizzle supports views but not refresh logic)
- Partial indexes with operator classes (`gin_trgm_ops`)
- Row-level security policies
- Domain types, custom collations, sequences with non-default options

For these, write a custom migration with `drizzle-kit generate --custom`. The command produces an empty SQL file under `drizzle/` with the correct numbering and journal entry. Edit it manually and document the reason in a leading SQL comment. Drizzle treats custom migrations as opaque, so the TypeScript schema has no counterpart.

## Verification (MANDATORY)

Before opening any PR that touches a schema file or a migration:

```bash
# 1. Run generate against the current schema. If Drizzle creates a new SQL
# file, the schema and migrations are out of sync. Investigate and fix
# before pushing.
pnpm exec drizzle-kit generate

# 2. Inspect the diff. If the previous step produced new files in
# drizzle/ or modified drizzle/_meta/_journal.json, the schema diverged.
# Revert the probe and write the missing migration intentionally.
git status drizzle/

# 3. Apply migrations to a fresh database and confirm they run cleanly.
pnpm exec drizzle-kit migrate
```

A non-empty output from step 1 is a blocking issue when the change was supposed to be drift-free.

## End-to-End Verification

When the change is non-trivial (new index, new column, new table, new relation):

1. Spin up a fresh database: `docker compose -f docker-compose.test.yml up -d`.
2. Run all migrations: `pnpm exec drizzle-kit migrate`.
3. Re-run `pnpm exec drizzle-kit generate`. If Drizzle generates a new file, the migration set is incomplete. Fix before pushing.
4. Run the full test suite. Any test that touches the changed table must pass against the fresh schema.

## Down Migrations

Drizzle has no built-in down migration support. The `drizzle-kit drop` command removes the most recent migration file and journal entry but does not run any rollback SQL against the database. A rollback is a new migration that reverses the previous change.

This has two consequences:

1. Never delete a migration file from `drizzle/` after it has been applied to any shared environment. The file is the audit trail. Removing it desynchronizes `__drizzle_migrations` from the file system.
2. To reverse a deployed change, write a new migration with the inverse DDL. Treat it like any other forward migration: name, generate, review, apply.

For data migrations that are irreversible (lossy conversions, truncation, deduplication), document the irreversibility in a leading SQL comment. There is no `down` method to throw from.

## Idempotency

Drizzle records applied migrations in the `__drizzle_migrations` table by content hash. The hash check is reliable for the happy path, but partial failures and hand-edited migration tables bypass it. Defend at the SQL level.

- `CREATE INDEX IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, `CREATE EXTENSION IF NOT EXISTS`.
- `DROP ... IF EXISTS` on every drop statement.
- `INSERT INTO ... ON CONFLICT DO NOTHING` for seed data inside migrations. Plain `INSERT` statements duplicate rows on a partial re-run.
- `DO $$ ... END $$` blocks for statements that have no native `IF NOT EXISTS` clause.

## Transactions

Drizzle wraps each migration file in a single transaction by default. For DDL that PostgreSQL cannot run inside a transaction (`CREATE INDEX CONCURRENTLY`, `ALTER TYPE ... ADD VALUE`, `VACUUM`, `REINDEX`), split the migration so the non-transactional statement lives in its own file. Drizzle has no per-file `transaction: false` flag, so the only safe approach is to isolate the statement.

## Schema Completeness

Every new table must include these columns and constraints before the PR is opened. Missing any of these is a review-blocking issue.

| Requirement | Rule |
|-------------|------|
| `created_at` | `timestamp('created_at').notNull().defaultNow()` on every table |
| `updated_at` | `timestamp('updated_at').notNull().defaultNow().$onUpdateFn(() => new Date())` on every table that can be modified after creation. Append-only tables, like audit logs and event logs, are exempt |
| `deleted_at` | `timestamp('deleted_at')` (nullable) when the table participates in soft delete. Add a partial index `where (deleted_at IS NULL)` for the common active-row filter |
| `company_id` index | `index('<Table>_companyId_idx').on(table.companyId)` on every table with a `company_id` column |
| Compound indexes | `index('<Table>_companyId_status_idx').on(table.companyId, table.status)` and `index('<Table>_companyId_createdAt_idx').on(table.companyId, table.createdAt)` when the table is filtered by status or sorted by date |
| Foreign key indexes | Every `.references()` column needs an explicit `index(...)` unless it is already covered by a `uniqueIndex` or `primaryKey` |
| Primary key types | Use `uuid('id').primaryKey().defaultRandom()` or `bigint` identity columns. Never use `serial` for new tables: PostgreSQL now recommends `GENERATED ALWAYS AS IDENTITY` and Drizzle supports it via `bigint(...).generatedAlwaysAsIdentity()` |

When adding a new table, run this checklist before committing:

1. Does it have `created_at` and `updated_at` with the correct defaults?
2. Does it have `index('<Table>_companyId_idx')` if it has a `company_id` column?
3. Do all `.references()` columns have explicit indexes?
4. Is the table in the test cleanup order in `test/setup.ts`?
5. Does the seed file create records for this table?
6. Does every `index()` and `uniqueIndex()` declaration include an explicit name?
7. For PostgreSQL: are primary key types `uuid` or `bigint` identity, not `serial`?

## Service Layer Boundary

Routers, controllers, API handlers, and React Server Components must never import the Drizzle client directly. All database operations go through service or repository modules. The controller imports the service interface; the service module imports the Drizzle client and the schema.

This is harder to enforce in Drizzle than in Prisma or TypeORM because Drizzle has no DI container of its own. Enforce it through ESLint boundaries (`eslint-plugin-boundaries`), a directory convention (`src/db/services/`), or both. A handler that imports from `src/db/schema/` is a defect.

## Type Safety Over Raw SQL

The `sql` template tag is an escape hatch, not a default. Every direct use of `db.execute(sql\`...\`)`, `db.run(sql\`...\`)`, or `sql.raw(...)` must be justified in a code comment that names what query builder method is insufficient.

Acceptable uses of `sql`:

- Recursive CTEs and window functions the query builder cannot express.
- Database-specific maintenance commands run by operational scripts.
- Migration files, when `drizzle-kit generate` cannot infer the change.

Every raw `sql` call outside these scopes must be replaced with the equivalent query builder call. The query builder preserves type safety from schema definitions through to result rows; raw `sql` does not.

## API Boundary Types

Never return Drizzle inferred row types directly from HTTP handlers. The schema type is shaped by storage concerns, not API contract concerns. A column rename or type narrowing then becomes a breaking API change for every consumer.

Define explicit DTOs at the API boundary. The handler returns `UserDTO`; the service returns the inferred row type; the API mapper converts. This keeps storage refactors independent of consumer impact.

## Migration Ordering

Drizzle uses an integer prefix on migration filenames (`0001_<slug>.sql`, `0002_<slug>.sql`) and tracks order in `drizzle/_meta/_journal.json`. Migrations for the current task must always have the latest numbers.

Before every commit, push, rebase, or PR:

1. List existing migrations: `ls drizzle | sort | tail -5`.
2. If your migrations are not last, regenerate them: delete your local migration files, restore `drizzle/_meta/_journal.json` from the base branch, then run `drizzle-kit generate` to renumber.
3. Verify ordering again after rebase. Rebasing can interleave your migrations with newly merged ones, breaking the journal hash chain.

A rebased branch with a stale journal is the most common cause of "phantom drift" reports.

## Common Drift Sources

These patterns produce schema drift in Drizzle projects. Detect them in review.

| Pattern | Why it drifts |
|---------|--------------|
| `drizzle-kit push` against any shared environment | The schema diverges from the migration file history with no record |
| Manual edit of a migration SQL file after `drizzle-kit generate` produced it | The journal hash no longer matches; some teammates re-run the migration, others do not |
| Two branches each adding a migration with the same number | One branch's migration silently overwrites the other after merge; the lost migration never applies in production |
| Renaming a column without using `drizzle-kit generate --custom` | Drizzle emits `DROP COLUMN; ADD COLUMN;` which drops data |
| Adding a `references()` without an explicit `index()` | Joins do full table scans; the drift shows up as latency, not as a SQL diff |

## Cross-References

- `~/.claude/rules/git-workflow.md` "Migration Ordering" and "Migration Idempotency" cover ordering and `IF NOT EXISTS` requirements.
- `~/.claude/rules/verification.md` "Database changes add" lists the verification gates.
- `~/.claude/checklists/checklist.md` category "Schema-Migration Sync" is the per-PR checklist.
- `~/.claude/rules/code-style.md` "No raw SQL" and "Service layer for data access" apply to Drizzle the same way they apply to Prisma.
- `~/.claude/rules/lang/prisma-migrations.md` is the parallel rule for Prisma; the conceptual structure is the same.

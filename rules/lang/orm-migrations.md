# ORM Migrations

Cross-cutting rules and per-ORM specifics for SQL ORM projects. Triggered when a task names Prisma, TypeORM, Drizzle, Sequelize, or MikroORM. Replaces the earlier per-ORM rule files.

## Core Principle

Schema definition code is the single source of truth. Every DDL statement in a migration file must have a matching declaration in the schema source. The migration history must, in turn, never include DDL that has no schema-source counterpart. Schema and migrations are two views of the same state. When they disagree, the next developer who runs migrations against a fresh database gets a phantom drift migration on the first generate or diff.

## Cross-Cutting Principles

### Schema Sync Strategy

Every ORM ships at least one shortcut for skipping the migration log: `synchronize: true`, `sync()`, `db push`, `schema:sync`, `schema:fresh`. These are development conveniences. They become defects the moment they touch a database with data.

| Environment | Schema sync allowed? | Migrations |
|-------------|---------------------|------------|
| Greenfield local dev | Yes, only during prototyping | Switch to migrations once the schema stabilizes |
| Mature local dev | No | Run migrations on startup or via CLI |
| Test | No, except `force` mode against a dedicated test database | Run before the suite |
| Staging | No | Run as a deployment step before the app boots |
| Production | No, hard requirement | Run as a deployment step before the app boots |

Configure the application bootstrap to refuse schema-sync calls when `NODE_ENV` is `production` or `staging`. CI must fail when a sync shortcut appears in deployment scripts.

### Parity Contract

For every ORM, the contract is the same:

| Migration SQL | Required in schema source |
|---------------|--------------------------|
| `CREATE TABLE` | Class, model, or table export |
| `DROP TABLE` | Class, model, or table export removed |
| `ALTER TABLE ADD COLUMN` | Field or column declaration |
| `ALTER TABLE DROP COLUMN` | Field or column declaration removed |
| `CREATE INDEX` | Index declaration with explicit name |
| `DROP INDEX` | Index declaration removed |
| `ALTER TABLE ADD CONSTRAINT FOREIGN KEY` | Relation declaration |
| `ALTER TABLE ADD CONSTRAINT CHECK` | Check declaration |

Per-ORM sections below show the exact syntax for each side of the contract.

### Index Naming Convention

Always pass an explicit name. Default naming strategies differ across ORMs: TypeORM hashes with SHA1 and truncates, Prisma derives from columns, Drizzle leaves the index anonymous when no name is provided, Sequelize concatenates table and column names. None of these match raw-SQL names from manual migrations, and all of them produce hard-to-diff drift.

Pattern: `<Table>_<col>(_<col>)*_<purpose>_idx`. Purposes: `lookup`, `search`, `sort`, `fk`, `partial`.

### Idempotent DDL

Every migration must be safe to run more than once. The migration log normally prevents re-execution, but partial failures, hand-edited migration tables, and team errors all bypass it. Defend at the SQL level.

- `IF NOT EXISTS` on `CREATE TABLE`, `CREATE INDEX`, `CREATE EXTENSION`, `CREATE SCHEMA`, `CREATE TYPE`
- `IF EXISTS` on every `DROP` statement
- `DO $$ ... END $$` blocks with explicit existence checks for statements that lack a native `IF NOT EXISTS` clause, such as `CREATE MATERIALIZED VIEW`, `CREATE POLICY`, and some `CREATE TRIGGER` dialects
- `INSERT INTO ... ON CONFLICT DO NOTHING` for any seed data inside migrations
- Never assume a clean slate. Another migration, a manual hotfix, or a partial deploy may have created the object already

### Transactional Migrations

Migrations run inside a transaction by default in Prisma, TypeORM, Drizzle, and MikroORM. Sequelize requires explicit transaction wiring per file.

For DDL that PostgreSQL cannot run inside a transaction, isolate it in its own migration file. Statements that need this treatment:

- `CREATE INDEX CONCURRENTLY`
- `ALTER TYPE ... ADD VALUE`
- `VACUUM`, `REINDEX`

Per-ORM sections cover the exact mechanism for disabling the wrapping transaction.

### Migration Ordering

Migrations for the current task must always have the latest sequence numbers or timestamps. Other team members may merge migrations while work is in progress.

Before every commit, push, rebase, or PR:

1. List existing migrations, sorted, last 5 shown
2. If the current branch's migrations are not last, regenerate or rename so they are
3. Verify ordering again after rebase. Rebasing can interleave migrations with newly merged ones

A rebased branch with a stale migration sequence is the most common cause of phantom drift reports.

### Down Migrations

Three ORMs require a working `down` function: TypeORM, Sequelize, MikroORM. Prisma rejects manual down migrations as a design choice; rollback is a new forward migration. Drizzle has no down migration support at all.

| ORM | Down mechanism |
|-----|---------------|
| Prisma | New forward migration with the inverse DDL. `prisma migrate reset` is destructive and never runs in production |
| TypeORM | `down(queryRunner)` method on the migration class. `migration:revert` calls it |
| Drizzle | None. New forward migration with the inverse DDL. Never delete a migration file from a shared environment |
| Sequelize | `down(queryInterface)` function. `db:migrate:undo` calls it |
| MikroORM | `down()` method on the migration class. `mikro-orm migration:down` calls it |

Migrations that perform irreversible data transformations like truncation, hash-based deduplication, and lossy conversions must throw in `down` with a message like `Migration <name> is irreversible. Restore from backup.`. Silent no-op `down` methods break revert semantics.

### Service Layer Boundary

Routers, controllers, API handlers, and Server Components must never import the ORM client, repository, or query API directly. All database operations go through service or repository modules. The handler imports the service interface; the service imports the ORM.

Enforce through:

- Directory convention: `src/services/`, `src/db/repositories/`
- ESLint boundaries: `eslint-plugin-boundaries`
- DI in projects that use a container

A handler that imports the ORM client is a defect. Move the query into a service method.

### No Raw SQL From App Code

Every ORM ships an escape hatch for raw SQL. None of them belongs in application code. Acceptable scopes:

- Migration files, when the operation cannot be expressed with the ORM's migration API
- Operations the query builder cannot express, like recursive CTEs or window functions. Wrap the raw call in a service method with a typed return signature, never in the calling code
- Database-specific maintenance commands like `VACUUM`, `REINDEX`, `ANALYZE` executed by operational scripts

Outside these scopes, every raw SQL call must be replaced with the equivalent ORM method. Raw SQL bypasses logging, hooks, type safety, and the query builder. Each ORM's raw-SQL escape hatch has a dedicated runtime hook that blocks it in application code.

### API Boundary Types

Never return ORM-inferred row types or ORM instances directly from HTTP handlers. The schema type is shaped by storage concerns, not API contract concerns. A column rename or type narrowing then becomes a breaking API change for every consumer. ORM instances also carry hidden methods like `save`, `update`, and `destroy` that change the response shape under `JSON.stringify`.

Define explicit DTOs at the API boundary. The handler returns a DTO; the service returns the ORM row or instance; the API mapper converts.

### Schema Completeness

Every new table or entity must include these fields before the PR is opened. Missing any of these is a review-blocking issue.

| Requirement | Rule |
|-------------|------|
| `createdAt` | Set automatically by the ORM on insert |
| `updatedAt` | Set automatically by the ORM on update. Append-only tables, like audit logs and event logs, are exempt |
| `deletedAt` | When the entity participates in soft delete. Combine with the ORM's archive-aware query mechanism |
| `companyId` index | Every tenant-scoped table needs an index on `companyId`. Without it, every query does a sequential scan |
| Compound indexes | Add `(companyId, status)` and `(companyId, createdAt)` when the entity is filtered by status or sorted by date |
| Foreign key indexes | Every relation needs an explicit index on the join column unless covered by a `UNIQUE` or `PRIMARY KEY` |
| Index naming | Every index, unique constraint, and check constraint must have an explicit name |

Per-ORM sections show the exact syntax. The reasons do not vary across ORMs: tenant isolation, FK join performance, and explicit naming for diff stability.

### Unmanaged Objects

Some PostgreSQL and MySQL objects cannot be expressed in any ORM's schema definition language:

- Extensions: `pg_trgm`, `uuid-ossp`, `pgcrypto`
- Custom triggers and functions
- Materialized views
- Partial indexes with operator classes, like `gin_trgm_ops`
- Expression indexes, like `CREATE INDEX ON x (lower(name))`
- Row-level security policies
- Domain types, custom collations, sequences with non-default options

For these, write raw SQL in the migration file and document the bypass reason in a leading comment. The ORM treats them as opaque DDL.

## Prisma

### Source of Truth

`schema.prisma` is the source. Every DDL statement in a migration file must have a matching declaration in `schema.prisma`.

### Parity Syntax

| Migration SQL | Required in `schema.prisma` |
|---------------|------------------------------|
| `CREATE INDEX <name> ON "<Model>" (...)` | `@@index([cols], map: "<name>")` on the model |
| `CREATE UNIQUE INDEX <name> ON "<Model>" (...)` | `@@unique([cols], map: "<name>")` on the model |
| `CREATE TABLE "<Model>"` | `model <Model>` block |
| Field added | Field on the model |
| Field removed | Field removed from the model |

### Index Naming in Prisma

Always pass `map:` explicitly:

```prisma
@@index([homeTeam], map: "Game_homeTeam_sportsbook_search_idx")
```

Default Prisma names collide with raw-SQL names and cause drift.

### Schema Completeness in Prisma

| Field | Declaration |
|-------|-------------|
| `createdAt` | `DateTime @default(now())` on every model |
| `updatedAt` | `DateTime @updatedAt` on every modifiable model |
| `companyId` index | `@@index([companyId])` on every tenant-scoped model |
| Compound indexes | `@@index([companyId, status])`, `@@index([companyId, createdAt])` |
| FK indexes | Every `@relation` field needs an `@@index` unless covered by `@@unique` |

### Verification in Prisma

Static parity check, offline:

```bash
pnpm exec prisma format --schema packages/database/prisma/schema.prisma
```

Authoritative drift check, requires a database:

```bash
pnpm exec prisma migrate diff \
  --from-schema-datamodel packages/database/prisma/schema.prisma \
  --to-migrations packages/database/prisma/migrations \
  --exit-code
```

`migrate diff --exit-code` returns 0 when schema and migrations agree. Non-zero exit is a blocking issue.

For non-trivial changes, run all migrations against a fresh database, then run `prisma migrate dev` with no name. If Prisma generates a new migration, the schema and migrations are out of sync.

### Down Migrations in Prisma

Prisma has no down migration. Rollback is a new forward migration with the inverse DDL.

### Raw Queries in Prisma

Prisma exposes raw-SQL escape hatches: the query-raw and execute-raw template tags and their unsafe variants. None of them belongs in application code. The dedicated runtime hook blocks them by default. The acceptable scopes are migrations and operations the query builder cannot express.

### Unmanaged Objects in Prisma

For PostgreSQL objects Prisma cannot express, set the `PRISMA_SCHEMA_SYNC_DISABLE=1` env var for that single migration write and document the bypass reason in a leading comment.

## TypeORM

### Source of Truth

Entity class decorators are the source. Every column, index, unique constraint, and relation declared on an entity must have a matching DDL statement in the migration history.

### Schema Sync Strategy in TypeORM

`synchronize` is the dangerous flag. Equivalent flags with the same blast radius:

- `migrationsRun: true` combined with `dropSchema: true`
- `dataSource.synchronize()` called from application code
- `dataSource.dropDatabase()` followed by `dataSource.synchronize()`

Never ship a build with any of these enabled outside local development.

### Parity Syntax

| Migration SQL | Required in entity decorators |
|---------------|------------------------------|
| `CREATE INDEX <name> ON "<Table>" (...)` | `@Index('<name>', ['col'])` on the entity or `@Index('<name>')` on the column |
| `CREATE UNIQUE INDEX <name> ON "<Table>" (...)` | `@Index('<name>', ['col'], { unique: true })` or `@Unique('<name>', ['col'])` |
| `CREATE TABLE "<Table>"` | `@Entity('<Table>')` class |
| `ADD CONSTRAINT <fk> FOREIGN KEY` | `@ManyToOne`, `@OneToMany`, `@OneToOne`, or `@ManyToMany` relation |
| `ADD CONSTRAINT <chk> CHECK` | `@Check('<name>', '<expression>')` on the entity |

### Index Naming in TypeORM

TypeORM's default naming strategy hashes table and column names with SHA1 and truncates to 27 characters. Names like `IDX_0b82f0b04f37c25a503fb3883c` are unreadable and collide with raw-SQL names. Always pass an explicit name as the first argument:

```typescript
@Entity('game')
@Index('Game_homeTeam_sportsbook_search_idx', ['homeTeam'])
@Index('Game_companyId_status_idx', ['companyId', 'status'])
export class Game {
  @PrimaryColumn() id: string;
  @Column() companyId: string;
  @Column() homeTeam: string;
  @Column() status: string;
}
```

For greenfield projects, install a custom `NamingStrategy` that produces deterministic, human-readable names. Apply it once at `DataSource` configuration time. Document the chosen pattern in an ADR.

### Schema Completeness in TypeORM

| Field | Declaration |
|-------|-------------|
| `createdAt` | `@CreateDateColumn()` on every entity |
| `updatedAt` | `@UpdateDateColumn()` on every modifiable entity |
| `deletedAt` | `@DeleteDateColumn()` when the entity participates in soft delete. Use `withDeleted: true` to include archived rows |
| `companyId` index | `@Index(['companyId'])` on every tenant-scoped entity |
| FK indexes | Every `@ManyToOne` join column needs `@Index` unless covered by `@Unique` or `@PrimaryColumn` |

### Verification in TypeORM

Generate a probe migration against the current entity state. A zero-byte output, or one that contains only an empty class, means the entity and migration history agree:

```bash
pnpm exec typeorm migration:generate \
  --dataSource src/data-source.ts \
  src/migrations/__probe__
```

Inspect the probe file. A non-empty probe is a blocking issue. Discard the probe after inspection:

```bash
rm -f src/migrations/__probe__-*.ts
```

For non-trivial changes, spin up a fresh database, run all migrations, re-run the probe. Then run the full test suite.

### Down Migrations in TypeORM

Every migration must implement a working `down`. `migration:revert` calls it.

| Operation in `up` | `down` must do |
|-------------------|---------------|
| `ADD COLUMN` | `DROP COLUMN` |
| `DROP COLUMN` | `ADD COLUMN` with original type, default, and nullability |
| `CREATE INDEX` | `DROP INDEX` with the same name |
| `CREATE TABLE` | `DROP TABLE` |

### Transactions in TypeORM

For non-transactional DDL, set `transaction = false` as a static field on the migration class:

```typescript
export class AddTrgmIndex20260514120000 implements MigrationInterface {
  public transaction = false;
  // up and down
}
```

### Raw Queries in TypeORM

Never call the raw query method on `queryRunner`, `manager`, `dataSource`, or `repository` from application code. The acceptable scopes are migrations, operations the query builder cannot express, and operational maintenance commands. The dedicated runtime hook blocks raw query calls in application code.

## Drizzle

### Source of Truth

TypeScript schema files under `src/db/schema/` are the source. Every column, index, unique constraint, foreign key, and check constraint declared in TypeScript must have a matching DDL statement under `drizzle/`.

### Schema Sync Strategy in Drizzle

Drizzle ships two distinct workflows. They are not interchangeable.

| Command | Effect | Use in |
|---------|--------|--------|
| `drizzle-kit generate` | Reads the TypeScript schema, diffs against `drizzle/_meta/_journal.json`, writes a new SQL migration file | Every environment |
| `drizzle-kit migrate` | Reads SQL files and applies any not yet in `__drizzle_migrations` | Every environment |
| `drizzle-kit push` | Diffs the TypeScript schema against the live database and executes DDL directly, no file | Local development only |
| `drizzle-kit pull` | Reads the live database, writes a TypeScript schema and a baseline migration | Onboarding only |

`drizzle-kit push` bypasses the migration file system. It can silently skip ambiguous changes like column renames or type narrowing, and leaves no SQL record. A staging or production environment that has ever been pushed against has no reliable migration history. Configure CI to fail when `push` appears in deployment scripts.

### Parity Syntax

| Migration SQL | Required in TypeScript schema |
|---------------|------------------------------|
| `CREATE INDEX <name> ON "<table>" (...)` | `index('<name>').on(table.col)` in the table's index callback |
| `CREATE UNIQUE INDEX <name> ON "<table>" (...)` | `uniqueIndex('<name>').on(table.col)` |
| `CREATE TABLE "<table>"` | `pgTable('<table>', ...)` export |
| `ADD CONSTRAINT <fk> FOREIGN KEY` | `.references(() => other.id)` on the column |
| `ADD CONSTRAINT <chk> CHECK` | `check('<name>', ...)` in the third argument with the SQL fragment |

### Index Naming in Drizzle

Always pass an explicit name. Drizzle does not auto-generate index names. Without an explicit name, the index is anonymous in SQL and cannot be referenced from later migrations.

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

### Schema Completeness in Drizzle

| Field | Declaration |
|-------|-------------|
| `created_at` | `timestamp('created_at').notNull().defaultNow()` |
| `updated_at` | `timestamp('updated_at').notNull().defaultNow().$onUpdateFn(() => new Date())` |
| `deleted_at` | `timestamp('deleted_at')`, nullable. Add a partial index on the common active-row filter |
| `company_id` index | `index('<Table>_companyId_idx').on(table.companyId)` |
| FK indexes | Every `.references()` column needs an explicit `index(...)` unless covered by `uniqueIndex` or `primaryKey` |
| Primary keys | `uuid('id').primaryKey().defaultRandom()` or `bigint(...).generatedAlwaysAsIdentity()`. Never `serial` for new tables |

### Verification in Drizzle

```bash
pnpm exec drizzle-kit generate
```

If Drizzle creates a new SQL file, the schema and migrations are out of sync. Inspect `git status drizzle/`. Apply to a fresh database with `pnpm exec drizzle-kit migrate` and confirm clean.

For non-trivial changes, spin up a fresh database, run all migrations, then re-run `drizzle-kit generate`. A new file means the migration set is incomplete.

### Down Migrations in Drizzle

Drizzle has no built-in down migration support. `drizzle-kit drop` removes the most recent migration file and journal entry but does not run any rollback SQL. Rollback is a new forward migration with the inverse DDL.

Two consequences:

1. Never delete a migration file from `drizzle/` after it has been applied to any shared environment. The file is the audit trail. Removing it desynchronizes `__drizzle_migrations` from the file system.
2. For data migrations that are irreversible, document the irreversibility in a leading SQL comment. There is no `down` method to throw from.

### Transactions in Drizzle

Drizzle wraps each migration file in a single transaction by default. For DDL that cannot run inside a transaction, split the statement into its own migration file. Drizzle has no per-file `transaction: false` flag.

### Raw SQL in Drizzle

The `sql` template tag is an escape hatch, not a default. Every direct use of the top-level execute or run methods with the SQL template tag, or the raw helper on the SQL builder, must be justified in a code comment that names what query builder method is insufficient. The dedicated runtime hook blocks these calls in application code.

Acceptable scopes: recursive CTEs, window functions, maintenance commands, and migration files.

### Migration Ordering in Drizzle

Drizzle uses integer-prefixed filenames like `0001_<slug>.sql` and tracks order in `drizzle/_meta/_journal.json`. Two branches each adding migration `0042` will silently overwrite one another after merge. Regenerate on rebase: delete local migration files, restore `drizzle/_meta/_journal.json` from the base branch, run `drizzle-kit generate`.

## Sequelize

### Source of Truth

Model definitions are the source: `Sequelize.define`, `Model.init`, or `@Table` with `sequelize-typescript`. Every column, index, unique constraint, association, and validator declared on a model must have a matching DDL statement in the migration history.

### Schema Sync Strategy in Sequelize

The `sync` family of methods is the dangerous shortcut. Three modes, three blast radii:

| Mode | Effect | Use in |
|------|--------|--------|
| `sync()` no options | Creates missing tables. Does not alter existing tables | Local dev only |
| `sync({ alter: true })` | Compares each model to the current table, runs `ALTER TABLE`. May drop columns | Local dev only, with care |
| `sync({ force: true })` | Drops every table and recreates them. Wipes all data | Test suite setup only |

Never call any form of `sync()` in staging or production. Configure the application bootstrap to refuse `sync()` calls when `NODE_ENV` is `production` or `staging`.

### Migration Tooling Choice

Pick one per project and document the choice in an ADR.

- `sequelize-cli`: convention-driven, stores state in `SequelizeMeta`, limited TypeScript support
- `umzug`: framework-agnostic, works with TypeScript out of the box, allows custom storage backends. Default storage is `SequelizeMeta` for compatibility

Whichever tool the project uses, never set the `umzug` storage to `none`. With no storage backend, every restart replays every migration.

### Parity Syntax

| Migration SQL | Required in model definition |
|---------------|------------------------------|
| `CREATE INDEX <name> ON "<table>" (...)` | `indexes: [{ name: '<name>', fields: ['col'] }]` in the model options |
| `CREATE UNIQUE INDEX <name> ON "<table>" (...)` | `indexes: [{ name: '<name>', fields: ['col'], unique: true }]` |
| `CREATE TABLE "<table>"` | `Model.init(...)` or `sequelize.define('<Table>', ...)` call |
| `ADD CONSTRAINT <fk> FOREIGN KEY` | `belongsTo`, `hasOne`, `hasMany`, or `belongsToMany` association |
| `ADD CONSTRAINT <chk> CHECK` | `validate` block or column-level `validate` option |

### Index Naming in Sequelize

Always pass an explicit `name` in every `indexes` entry. The default is `<table>_<fields>`, which collides with raw-SQL index names and produces ambiguous diffs.

```typescript
@Table({
  tableName: 'game',
  indexes: [
    { name: 'Game_homeTeam_sportsbook_search_idx', fields: ['homeTeam'] },
    { name: 'Game_companyId_status_idx', fields: ['companyId', 'status'] },
    { name: 'Game_companyId_createdAt_idx', fields: ['companyId', 'createdAt'] },
  ],
})
export class Game extends Model {
  @PrimaryKey @Column(DataType.UUID) declare id: string;
  @AllowNull(false) @Column(DataType.UUID) declare companyId: string;
  @AllowNull(false) @Column(DataType.STRING) declare homeTeam: string;
}
```

### Schema Completeness in Sequelize

| Field | Declaration |
|-------|-------------|
| `timestamps` | `timestamps: true`, the default. Sequelize creates `createdAt` and `updatedAt` automatically |
| `paranoid` | `paranoid: true` for soft delete. Requires `timestamps: true`. Creates `deletedAt` and filters all default queries |
| `underscored` | Pick a project-wide convention and document it in an ADR. Never mix conventions within the same database |
| `companyId` index | `indexes: [{ name: '<Table>_companyId_idx', fields: ['companyId'] }]` |
| FK indexes | `belongsTo` does not create an index on the foreign key. Add an explicit `indexes` entry for every `belongsTo` |
| Primary keys | `DataType.UUID` with `defaultValue: DataTypes.UUIDV4` or `BIGINT` with `autoIncrement: true` |

### Verification in Sequelize

Sequelize does not ship a built-in `migrate diff` command. The verification flow uses a controlled environment:

```bash
# 1. Fresh database
docker compose -f docker-compose.test.yml up -d

# 2. Apply all migrations
pnpm exec sequelize-cli db:migrate
# or, for umzug projects:
pnpm exec ts-node src/db/migrate.ts up

# 3. Boot the app with sync({ alter: false }) and read the log output.
#    Any "ALTER TABLE" or "CREATE INDEX" indicates drift.

# 4. Run the full test suite.
```

A model that requires `sync({ alter: true })` to match the migrated schema is a blocking issue.

For non-trivial changes, also run all migrations in reverse with `db:migrate:undo:all`. The database must end up empty. Then run all forward again. The result must be identical to the first forward run. A migration set that does not round-trip is a defect.

### Down Migrations in Sequelize

| Operation in `up` | `down` must do |
|-------------------|---------------|
| `queryInterface.addColumn(...)` | `queryInterface.removeColumn(...)` |
| `queryInterface.removeColumn(...)` | `queryInterface.addColumn(...)` with original type, default, `allowNull` |
| `queryInterface.addIndex(...)` | `queryInterface.removeIndex(...)` with the same name |
| `queryInterface.createTable(...)` | `queryInterface.dropTable(...)` |

When `dropTable` runs in `down` on PostgreSQL, pass an options object: `queryInterface.dropTable('foo', {})`. Omitting it causes intermittent rollback errors on certain Sequelize versions.

### Transactions in Sequelize

Every migration must run inside a transaction. The `up` and `down` functions receive a `queryInterface` whose methods accept a `transaction` option. Open a transaction and pass it to every call:

```typescript
import { QueryInterface, Sequelize, DataTypes } from 'sequelize';

export default {
  async up(queryInterface: QueryInterface, sequelize: Sequelize): Promise<void> {
    const transaction = await queryInterface.sequelize.transaction();
    try {
      await queryInterface.addColumn('game', 'company_id',
        { type: DataTypes.UUID, allowNull: false },
        { transaction });
      await queryInterface.addIndex('game', {
        name: 'Game_companyId_idx',
        fields: ['company_id'],
        transaction,
      });
      await transaction.commit();
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  },
};
```

For non-transactional DDL, split the operation into its own migration file and run it without a transaction wrapper.

### Raw Queries in Sequelize

Never call the raw query API from application code with a raw SQL string. The method bypasses model hooks, validation, scopes, and the type system. The dedicated runtime hook blocks raw query calls in application code. The acceptable scopes are migrations, operations the query builder cannot express, and operational maintenance commands.

### Migration Ordering in Sequelize

Filenames follow the pattern `YYYYMMDDHHMMSS-<slug>.js` or `.ts`. If `umzug` is configured with a non-default file pattern, verify that the pattern matches what the CLI also accepts. A mismatch causes migrations to apply with one tool and be invisible to the other.

## MikroORM

### Source of Truth

Entity class decorators are the source. MikroORM uses Data Mapper plus Unit of Work patterns. The entity definitions live under whatever paths `entities` and `entitiesTs` point at in the `MikroORM.init()` config.

### Entity Discovery

The discovery layer reads entity classes at boot. Two config keys matter:

| Key | Use |
|-----|-----|
| `entities` | Paths to compiled JS entity files for production |
| `entitiesTs` | Paths to TS source files for CLI commands like `mikro-orm migration:create` |

Both must be set when the project uses folder-based discovery. Missing `entitiesTs` causes the CLI to fall back to compiled output, which is stale during development.

### Schema Sync Strategy in MikroORM

MikroORM ships several schema shortcuts. None of them belong outside local development:

| Command | Effect | Use in |
|---------|--------|--------|
| `mikro-orm schema:fresh` | Drops and recreates the entire schema from entities. Wipes all data | Local dev only |
| `mikro-orm schema:update` | Diffs entities against the live database and runs DDL | Local dev only |
| `mikro-orm schema:create` | Outputs the full schema as SQL | Inspection only |
| `mikro-orm migration:create` | Generates a new migration file from the entity-vs-database diff | Every environment |
| `mikro-orm migration:up` | Applies pending migrations | Every environment |
| `mikro-orm migration:down` | Reverts the most recent migration | Every environment |

Configure CI to fail when `schema:fresh` or `schema:update` appears in deployment scripts.

### Migrator Setup

Install `@mikro-orm/migrations` for SQL drivers or `@mikro-orm/migrations-mongodb` for MongoDB. Register the Migrator extension in the ORM config:

```typescript
import { defineConfig } from '@mikro-orm/postgresql';
import { Migrator } from '@mikro-orm/migrations';

export default defineConfig({
  // ...
  extensions: [Migrator],
  migrations: {
    path: 'dist/migrations',
    pathTs: 'src/migrations',
    transactional: true,
    allOrNothing: true,
    emit: 'ts',
  },
});
```

`transactional: true` wraps each migration in its own transaction. `allOrNothing: true` wraps the entire migration batch in a master transaction so a mid-batch failure rolls everything back.

### Parity Syntax

| Migration SQL | Required in entity decorators |
|---------------|------------------------------|
| `CREATE INDEX <name> ON "<table>" (...)` | `@Index({ name: '<name>', properties: ['col'] })` on the entity |
| `CREATE UNIQUE INDEX <name> ON "<table>" (...)` | `@Unique({ name: '<name>', properties: ['col'] })` |
| `CREATE TABLE "<table>"` | `@Entity({ tableName: '<table>' })` class |
| `ADD CONSTRAINT <fk> FOREIGN KEY` | `@ManyToOne`, `@OneToMany`, `@OneToOne`, `@ManyToMany` relation |
| `ADD CONSTRAINT <chk> CHECK` | `@Check({ name: '<name>', expression: '...' })` |

### Index Naming in MikroORM

Always pass an explicit `name`. MikroORM's default naming uses the SchemaHelper which produces deterministic but verbose names. The same `<Table>_<col>(_<col>)*_<purpose>_idx` pattern keeps diffs readable:

```typescript
@Entity({ tableName: 'game' })
@Index({ name: 'Game_homeTeam_sportsbook_search_idx', properties: ['homeTeam'] })
@Index({ name: 'Game_companyId_status_idx', properties: ['companyId', 'status'] })
export class Game {
  @PrimaryKey()
  id!: string;

  @Property()
  companyId!: string;

  @Property()
  homeTeam!: string;

  @Property()
  status!: string;
}
```

### Schema Completeness in MikroORM

| Field | Declaration |
|-------|-------------|
| `createdAt` | `@Property({ onCreate: () => new Date() })` or use the project's base entity |
| `updatedAt` | `@Property({ onCreate: () => new Date(), onUpdate: () => new Date() })` |
| `deletedAt` | `@Property({ nullable: true })` plus a soft-delete filter on the entity |
| `companyId` index | `@Index({ name: '<Table>_companyId_idx', properties: ['companyId'] })` on every tenant-scoped entity |
| FK indexes | `@ManyToOne` relations do not auto-index. Add `@Index` on the join column unless covered by `@Unique` |

Soft-delete filtering uses MikroORM's `@Filter` decorator:

```typescript
@Entity()
@Filter({ name: 'softDelete', cond: { deletedAt: null }, default: true })
export class Order {
  @Property({ nullable: true })
  deletedAt?: Date;
}
```

### Verification in MikroORM

Generate a probe migration. A zero-diff output means the entity and migration history agree:

```bash
pnpm exec mikro-orm migration:create --dry-run
```

If the output is non-empty, the schema and migrations are out of sync. Investigate before pushing.

For non-trivial changes, spin up a fresh database, run all migrations, then re-run the dry-run. A non-empty diff means the migration set is incomplete.

### Initial Migration

For a new project, generate the baseline migration once:

```bash
pnpm exec mikro-orm migration:create --initial
```

`--initial` produces a migration that creates the entire schema from current entities. Use it only at project bootstrap. Never run it on an existing schema; it will conflict with whatever is already there.

### Down Migrations in MikroORM

Every migration has `up` and `down` methods. `migration:down` calls `down` on the most recent migration. The same rules as TypeORM apply: irreversible operations must throw in `down` with a clear message.

### Transactions in MikroORM

With `transactional: true` in config, MikroORM wraps each migration in its own transaction. The optional `allOrNothing: true` wraps the entire batch in a master transaction. Override on a per-migration basis by setting `disableForeignKeys = true` or by writing raw SQL outside the wrapper when needed.

### EntityManager Boundary

Routers, controllers, and API handlers must never import the `EntityManager` directly. All database operations go through service modules that fork the EntityManager per-request via `RequestContext`.

```typescript
// Service
export class OrderService {
  constructor(private readonly em: EntityManager) {}

  async findActive(companyId: string): Promise<Order[]> {
    return this.em.fork().find(Order, { companyId, deletedAt: null });
  }
}
```

Always `fork()` per request. The Unit of Work pattern means a shared EntityManager accumulates state across requests, which causes data leakage and memory growth.

### Raw Queries in MikroORM

Use the QueryBuilder, not raw SQL. When the query builder cannot express the operation, MikroORM exposes a direct execute method on the EntityManager and the underlying Knex instance for SQL-driver projects. The acceptable scopes are the same as other ORMs: migrations, expressions the query builder cannot capture, and operational maintenance.

## Common Drift Sources

These patterns produce schema drift in any ORM project. Detect them in review.

| Pattern | Why it drifts |
|---------|--------------|
| Schema-sync shortcut in staging or production | The schema mutates without writing a migration; the team loses the audit trail |
| Adding a column to an entity or model without a matching migration | Local tests pass against the sync-mutated schema; production deployment fails when the column is missing |
| Renaming a property without a `name:` argument on the decorator | The next generate produces `DROP COLUMN <old>; ADD COLUMN <new>;`, which drops data |
| Index declared without an explicit name on one branch, with an explicit name on another | Two migrations create different index names for the same logical index. Both apply; one becomes orphaned |
| Two branches each adding a migration with the same sequence number | One branch's migration silently overwrites the other after merge. The lost migration never applies in production |
| Manual edit of a migration SQL file after generation | The hash check no longer matches; some teammates re-run the migration, others do not |
| Mixed `foreignKey:` naming on the two sides of a relation | The ORM generates two columns or two foreign keys with similar names. Only one is in the migration |
| ESM/CommonJS module format mismatch between the migrator config and migration files | Migrations silently fail to load. The tool reports zero pending migrations on a brand-new database |
| Migrator storage set to no-op or in-memory | No record of what ran. Every restart replays every migration |
| Adding a soft-delete decorator without a migration that adds the corresponding column | All queries break: the ORM adds a filter against a column that does not exist |

## Cross-References

- [`rules/git-workflow.md`](../git-workflow.md) "Migration Ordering" and "Migration Idempotency" cover timestamp ordering and `IF NOT EXISTS` requirements
- [`rules/verification.md`](../verification.md) "Database changes add" lists the verification gates
- [`checklists/checklist.md`](../../checklists/checklist.md) category "Schema-Migration Sync" is the per-PR checklist
- [`rules/code-style.md`](../code-style.md) "No raw SQL" and "Service layer for data access" cover the cross-ORM boundary
- [`standards/postgresql.md`](../../standards/postgresql.md) covers PostgreSQL-specific concerns including PG 18 features and native `uuidv7()`
- [`standards/identifiers.md`](../../standards/identifiers.md) covers identifier choice for primary keys

## Enforcement

Enforced by: [`hooks/drizzle-raw-sql-blocker.py`](../hooks/drizzle-raw-sql-blocker.py).
Enforced by: [`hooks/drizzle-schema-sync.py`](../hooks/drizzle-schema-sync.py).
Enforced by: [`hooks/migration-idempotency.py`](../hooks/migration-idempotency.py).
Enforced by: [`hooks/prisma-raw-sql-blocker.py`](../hooks/prisma-raw-sql-blocker.py).
Enforced by: [`hooks/prisma-schema-sync.py`](../hooks/prisma-schema-sync.py).
Enforced by: [`hooks/sequelize-raw-sql-blocker.py`](../hooks/sequelize-raw-sql-blocker.py).
Enforced by: [`hooks/sequelize-schema-sync.py`](../hooks/sequelize-schema-sync.py).
Enforced by: [`hooks/typeorm-raw-sql-blocker.py`](../hooks/typeorm-raw-sql-blocker.py).
Enforced by: [`hooks/typeorm-schema-sync.py`](../hooks/typeorm-schema-sync.py).

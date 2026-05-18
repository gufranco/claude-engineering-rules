# Sequelize Migrations

## Core Rule

Model definitions (`Sequelize.define`, `Model.init`, or `@Table` with `sequelize-typescript`) are the single source of truth for the schema. Every column, index, unique constraint, association, and validator declared on a model must have a matching DDL statement in the migration history. The migration history must, in turn, never include DDL that has no model counterpart. Code and migrations are two views of the same state. When they disagree, the next developer who runs the test suite against a fresh database gets a model that fails to query the columns it claims to have.

## Schema Sync Strategy (MANDATORY)

`Sequelize.sync()` is a development convenience that rewrites the schema in place. It has three modes, each with a different blast radius. Configure the call site explicitly per environment.

| `sync` mode | Effect | Use in |
|-------------|--------|--------|
| `sync()` (no options) | Creates missing tables. Does not alter existing tables | Local development only |
| `sync({ alter: true })` | Compares each model to the current table and runs `ALTER TABLE` to reconcile. May drop columns or change types | Local development only, with care |
| `sync({ force: true })` | Drops every table and recreates them from the models. Wipes all data | Test suite setup only |

Never call any form of `sync()` in staging or production. Every schema change in those environments must go through a migration file. Configure the application bootstrap to read `process.env.NODE_ENV` and refuse to call `sync()` when the value is `production` or `staging`. CI must fail when an application module calls `sync` from a code path that runs in those environments.

The recommended workflow:

1. Local development: prefer migrations from day one. `sync()` is acceptable for greenfield prototyping; switch to migrations as soon as the schema stabilizes.
2. Test: `sync({ force: true })` in the test bootstrap, against a dedicated test database that has no production data.
3. Staging and production: migration files only, applied as a deployment step before the app boots.

## Migration Tooling Choice

Sequelize ships `sequelize-cli` for migrations. The `umzug` library is the more flexible alternative and integrates better with TypeScript projects. Pick one per project and document the choice in an ADR.

- `sequelize-cli`: convention-driven, generates migration files with `up` and `down`, stores state in `SequelizeMeta`. Limited TypeScript support.
- `umzug`: framework-agnostic, works with TypeScript out of the box, allows custom storage backends. Storage default is `SequelizeMeta` for compatibility.

Whichever tool the project uses, never set the `umzug` storage to `none`. With no storage backend, the tool has no record of what migrations ran. A re-run will execute every migration again from the top.

## Parity Requirements

| Migration SQL | Required in model definition |
|---------------|------------------------------|
| `CREATE INDEX <name> ON "<table>" (...)` | `indexes: [{ name: '<name>', fields: ['col'] }]` in the model options |
| `CREATE UNIQUE INDEX <name> ON "<table>" (...)` | `indexes: [{ name: '<name>', fields: ['col'], unique: true }]` |
| `ALTER TABLE "<table>" ADD COLUMN "<col>"` | Attribute in the model attributes object |
| `ALTER TABLE "<table>" DROP COLUMN "<col>"` | Attribute removed from the model |
| `DROP INDEX <name>` | `indexes` entry removed from the model options |
| `CREATE TABLE "<table>"` | `Model.init(...)` or `sequelize.define('<Table>', ...)` call |
| `DROP TABLE "<table>"` | Model definition removed |
| `ALTER TABLE ... ADD CONSTRAINT "<fk>" FOREIGN KEY ...` | `belongsTo`, `hasOne`, `hasMany`, or `belongsToMany` association |
| `ALTER TABLE ... ADD CONSTRAINT "<chk>" CHECK ...` | `validate` block or column-level `validate` option |

## Index Naming Convention

Always pass an explicit `name` in every `indexes` entry. The default naming strategy is `<table>_<fields>`, which collides with raw-SQL index names and produces ambiguous diffs when fields are renamed.

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
  @PrimaryKey
  @Column(DataType.UUID)
  declare id: string;

  @AllowNull(false)
  @Column(DataType.UUID)
  declare companyId: string;

  @AllowNull(false)
  @Column(DataType.STRING)
  declare homeTeam: string;
}
```

Pattern: `<Table>_<col>(_<col>)*_<purpose>_idx`. Purposes: `lookup`, `search`, `sort`, `fk`, `partial`.

## Unmanaged Objects

Some PostgreSQL and MySQL objects cannot be expressed in Sequelize model definitions:

- Extensions (`pg_trgm`, `uuid-ossp`, `pgcrypto`)
- Custom triggers and functions
- Materialized views
- Partial indexes with operator classes (`gin_trgm_ops`)
- Expression indexes (`CREATE INDEX ON x (lower(name))`)
- Row-level security policies
- Domain types and custom collations

For these, write raw SQL inside the migration's `up` and `down` using `queryInterface.sequelize.query('...', { transaction })`. Document the bypass reason in a leading comment.

## Verification (MANDATORY)

Sequelize does not ship a built-in `migrate diff` command. The verification flow uses a controlled environment instead.

Before opening any PR that touches a migration file or a model:

```bash
# 1. Spin up a fresh database.
docker compose -f docker-compose.test.yml up -d

# 2. Apply all migrations.
pnpm exec sequelize-cli db:migrate
# or, for umzug projects:
pnpm exec ts-node src/db/migrate.ts up

# 3. Boot the application with sync({ alter: false }) and read the
# Sequelize log output. Any "ALTER TABLE" or "CREATE INDEX" that
# would run during sync indicates drift between models and migrations.

# 4. Run the full test suite. The suite must boot against the migrated
# schema without errors.
```

A model that requires `sync({ alter: true })` to match the migrated schema is a blocking issue. Write the missing migration before pushing.

## End-to-End Verification

When the change is non-trivial (new index, new column, new model, new association):

1. Spin up a fresh database (see above).
2. Run all migrations.
3. Run all migrations in reverse with `db:migrate:undo:all` (or the umzug equivalent). The database must end up empty.
4. Run all migrations forward again. The result must be identical to step 2.
5. Run the full test suite against the final state.

A migration set that does not round-trip is a defect. Down migrations must restore the previous state exactly.

## Down Migrations

Every migration must implement a working `down`. Sequelize's `db:migrate:undo` calls `down` for the most recent migration. A no-op `down` is a defect.

| Operation in `up` | `down` must do |
|-------------------|---------------|
| `queryInterface.addColumn(...)` | `queryInterface.removeColumn(...)` |
| `queryInterface.removeColumn(...)` | `queryInterface.addColumn(...)` with the original type, default, and `allowNull` |
| `queryInterface.addIndex(...)` | `queryInterface.removeIndex(...)` with the same name |
| `queryInterface.createTable(...)` | `queryInterface.dropTable(...)` |
| Data transformation | Reverse transformation when reversible. When irreversible, throw an explicit error |

Migrations that perform irreversible data transformations (truncation, hash-based deduplication, lossy conversions) must throw in `down` with the message `Migration <name> is irreversible. Restore from backup.`. Silent no-op `down` methods break `db:migrate:undo` semantics.

When `dropTable` runs in `down` on PostgreSQL, pass an options object as the second argument: `queryInterface.dropTable('foo', {})`. Omitting it causes intermittent rollback errors on certain Sequelize versions.

## Transactions

Every migration must run inside a transaction. The `up` and `down` functions receive a `queryInterface` whose methods accept a `transaction` option. Open a transaction and pass it to every call.

```typescript
import { QueryInterface, Sequelize, DataTypes } from 'sequelize';

export default {
  async up(queryInterface: QueryInterface, sequelize: Sequelize): Promise<void> {
    const transaction = await queryInterface.sequelize.transaction();
    try {
      await queryInterface.addColumn(
        'game',
        'company_id',
        { type: DataTypes.UUID, allowNull: false },
        { transaction },
      );
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

  async down(queryInterface: QueryInterface): Promise<void> {
    const transaction = await queryInterface.sequelize.transaction();
    try {
      await queryInterface.removeIndex('game', 'Game_companyId_idx', { transaction });
      await queryInterface.removeColumn('game', 'company_id', { transaction });
      await transaction.commit();
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  },
};
```

`queryInterface.addColumn` on some Sequelize versions ignores the `transaction` option when combined with the `after` option. Verify with the installed Sequelize version before relying on transactional `addColumn` plus column ordering.

For DDL that PostgreSQL cannot run inside a transaction (`CREATE INDEX CONCURRENTLY`, `ALTER TYPE ... ADD VALUE`, `VACUUM`), split the operation into its own migration and run it without a transaction wrapper.

## Schema Completeness

Every new model must include these attributes and options before the PR is opened. Missing any of these is a review-blocking issue.

| Requirement | Rule |
|-------------|------|
| `timestamps` | `timestamps: true` (default) on every model. Sequelize creates `createdAt` and `updatedAt` automatically |
| `paranoid` | `paranoid: true` (and `timestamps: true`, which it requires) when the model participates in soft delete. Creates a `deletedAt` column and adds it to every default query |
| `underscored` | Pick a project-wide convention (`underscored: true` for snake_case columns, default for camelCase) and document it in an ADR. Never mix conventions within the same database |
| `companyId` index | `indexes: [{ name: '<Table>_companyId_idx', fields: ['companyId'] }]` on every model with a `companyId` column |
| Compound indexes | `indexes: [{ name: '<Table>_companyId_status_idx', fields: ['companyId', 'status'] }]` and `<Table>_companyId_createdAt_idx` when the model is filtered by status or sorted by date |
| Foreign key indexes | `belongsTo` does not create an index on the foreign key column. Add an explicit `indexes` entry for every `belongsTo` foreign key |
| Primary keys | Use `DataType.UUID` with `defaultValue: DataTypes.UUIDV4` or `BIGINT` with `autoIncrement: true`. Document the choice in an ADR |
| Naming | Every `indexes` entry must have an explicit `name` field |

When adding a new model, run this checklist before committing:

1. Does it have `timestamps: true`?
2. Does it have `indexes: [{ name: '<Table>_companyId_idx', fields: ['companyId'] }]` if it has a `companyId` column?
3. Do all `belongsTo` foreign key columns have explicit indexes?
4. Is the model in the test cleanup order in `test/setup.ts`?
5. Does the seed file create records for this model?
6. Does every `indexes` entry have an explicit `name`?

## Service Layer Boundary

Routers, controllers, and API handlers must never import a Sequelize `Model` class directly. All database operations go through service or repository modules. The controller imports the service; the service imports the model and the Sequelize instance.

A controller that calls `User.findOne(...)` is a defect. Move the query into `UserService.findById(...)`. Enforce through directory convention (`src/services/`, `src/db/repositories/`) and ESLint boundaries (`eslint-plugin-boundaries`).

## Type-Safe Queries Over Raw SQL

Never call `sequelize.query(...)` from application code with a raw SQL string. The method bypasses model hooks, validation, scopes, and the type system.

Acceptable uses of `sequelize.query`:

- Migration files, when the operation cannot be expressed with `queryInterface` methods.
- Operations the query builder cannot express, like window functions or recursive CTEs. Wrap the raw call in a service method with a typed return signature, never in calling code.
- Database-specific maintenance commands (`VACUUM`, `REINDEX`, `ANALYZE`) executed by operational scripts.

Every raw `sequelize.query` call outside these scopes must be replaced with the equivalent `findAll`, `findOne`, `update`, `destroy`, or `bulkCreate` invocation, or with a typed repository method.

## API Boundary Types

Never serialize Sequelize `Model` instances directly to HTTP responses. Sequelize instances carry hidden methods (`save`, `update`, `destroy`) and lazy-loaded associations that change the response shape depending on what was queried.

Define explicit DTOs at the API boundary. The handler returns `UserDTO`; the service returns the `Model` instance; the API mapper converts. This keeps storage refactors independent of consumer impact, and prevents accidental method exposure through `JSON.stringify`.

## Migration Ordering

Sequelize migration filenames follow the pattern `YYYYMMDDHHMMSS-<slug>.js` or `.ts`. Migrations for the current task must always have the latest timestamps.

Before every commit, push, rebase, or PR:

1. List existing migrations: `ls migrations | sort | tail -5`.
2. If your migrations are not last, rename them with newer timestamps.
3. Verify ordering again after rebase. Rebasing can interleave your migrations with newly merged ones.

If `umzug` is configured with a non-default file pattern, verify that the pattern matches what Sequelize's CLI also accepts. A mismatch causes migrations to apply with one tool and be invisible to the other.

## Idempotency

Every migration must be safe to run more than once. The `SequelizeMeta` log normally prevents re-execution, but partial failures, hand-edited meta tables, and team errors all bypass it. Defend at the SQL level.

- `IF NOT EXISTS` on `CREATE TABLE`, `CREATE INDEX`, `CREATE EXTENSION`, `CREATE SCHEMA`, `CREATE TYPE` (when using raw SQL).
- `IF EXISTS` on every `DROP` statement.
- `queryInterface.addColumn` and similar methods do not have an `IF NOT EXISTS` option. Wrap them in a `try/catch` only when the migration is genuinely additive and safe to re-run; otherwise let the failure surface so a developer can investigate.
- `DO $$ ... END $$` blocks with explicit existence checks for statements that lack a native `IF NOT EXISTS` clause.

## Common Drift Sources

These patterns produce schema drift in Sequelize projects. Detect them in review.

| Pattern | Why it drifts |
|---------|--------------|
| `sequelize.sync()` called on application boot in staging or production | The schema mutates without writing a migration; the team loses the audit trail |
| Adding a column to a model without a migration | Local tests pass against the `sync`-mutated schema; production deployment fails when the column is missing |
| `belongsTo` declared with `foreignKey: 'company_id'` on one side and `foreignKey: 'companyId'` on the other | Sequelize generates two columns or two foreign keys with similar names; only one is in the migration |
| ESM/CommonJS module format mismatch between `umzug` config and migration files | Migrations silently fail to load; the tool reports zero pending migrations on a brand-new database |
| `umzug` storage set to `none` | No record of what ran; every restart replays every migration |
| `paranoid: true` added to an existing model without a migration that adds `deletedAt` | All queries break: Sequelize adds `WHERE deleted_at IS NULL` against a column that does not exist |

## Cross-References

- `~/.claude/rules/git-workflow.md` "Migration Ordering" and "Migration Idempotency" cover timestamp ordering and `IF NOT EXISTS` requirements.
- `~/.claude/rules/verification.md` "Database changes add" lists the verification gates.
- `~/.claude/checklists/checklist.md` category "Schema-Migration Sync" is the per-PR checklist.
- `~/.claude/rules/code-style.md` "No raw SQL" and "Service layer for data access" apply to Sequelize the same way they apply to Prisma.
- `~/.claude/rules/lang/prisma-migrations.md` is the parallel rule for Prisma; the conceptual structure is the same.

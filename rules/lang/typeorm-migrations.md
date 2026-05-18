# TypeORM Migrations

## Core Rule

Entity class decorators are the single source of truth for the schema. Every column, index, unique constraint, and relation declared on an entity must have a matching DDL statement in the migration history. The migration history must, in turn, never include DDL that has no decorator counterpart. Code and migrations are two views of the same state. When they disagree, every developer who runs migrations against a fresh database gets a phantom drift migration on the next `migration:generate` run.

## Schema Sync Strategy (MANDATORY)

`synchronize` is a development-only convenience that diverges from migration history the moment data exists. Configure it explicitly per environment.

| Environment | `synchronize` | Migrations |
|-------------|---------------|------------|
| Local development | `false` (recommended) or `true` (only for greenfield prototyping) | Run on startup or via CLI |
| Test | `false` | Run before the test suite, against a dedicated test database |
| Staging | `false` | Run as a deployment step before the app boots |
| Production | `false` (hard requirement) | Run as a deployment step before the app boots |

Never ship a build with `synchronize: true` to staging or production. The flag triggers `ALTER TABLE` statements against the live database on every entity change. It bypasses the migration log, drops indexes silently, and reorders columns without warning. A single deployment with `synchronize: true` can wipe data that the application has not seen yet.

Equivalent flags that have the same blast radius and must also be `false` outside local development:

- `migrationsRun: true` combined with `dropSchema: true`
- `dataSource.synchronize()` called from application code
- `dataSource.dropDatabase()` followed by `dataSource.synchronize()`

## Parity Requirements

| Migration SQL | Required in entity decorators |
|---------------|------------------------------|
| `CREATE INDEX <name> ON "<Table>" (...)` | `@Index('<name>', ['col'])` on the entity or `@Index('<name>')` on the column |
| `CREATE UNIQUE INDEX <name> ON "<Table>" (...)` | `@Index('<name>', ['col'], { unique: true })` or `@Unique('<name>', ['col'])` |
| `ALTER TABLE "<Table>" ADD COLUMN "<col>"` | `@Column(...)` on the entity class |
| `ALTER TABLE "<Table>" DROP COLUMN "<col>"` | Field removed from the entity class |
| `DROP INDEX <name>` | `@Index` removed from the entity or column |
| `CREATE TABLE "<Table>"` | `@Entity('<Table>')` class |
| `DROP TABLE "<Table>"` | `@Entity` class removed |
| `ALTER TABLE "<Table>" ADD CONSTRAINT "<fk>" FOREIGN KEY ...` | `@ManyToOne`, `@OneToMany`, `@OneToOne`, or `@ManyToMany` relation |
| `ALTER TABLE "<Table>" ADD CONSTRAINT "<chk>" CHECK ...` | `@Check('<name>', '<expression>')` on the entity |

## Index Naming Convention

TypeORM's default naming strategy hashes table and column names with SHA1 and truncates to 27 characters. Names like `IDX_0b82f0b04f37c25a503fb3883c` are unreadable, collide with raw-SQL names from manual migrations, and force developers to grep the entire codebase to identify what an index covers. Always pass an explicit name as the first argument.

```typescript
@Entity('game')
@Index('Game_homeTeam_sportsbook_search_idx', ['homeTeam'])
@Index('Game_companyId_status_idx', ['companyId', 'status'])
export class Game {
  @PrimaryColumn()
  id: string;

  @Column()
  companyId: string;

  @Column()
  homeTeam: string;

  @Column()
  status: string;
}
```

Pattern: `<Entity>_<col>(_<col>)*_<purpose>_idx`. Purposes: `lookup`, `search`, `sort`, `fk`, `partial`.

### Custom Naming Strategy

For greenfield projects, install a custom `NamingStrategy` that produces deterministic, human-readable names without requiring per-decorator overrides. The strategy must implement `indexName`, `uniqueConstraintName`, `foreignKeyName`, `primaryKeyName`, and `checkConstraintName`. Apply it once at `DataSource` configuration time. Document the chosen pattern in an ADR so the team does not invent a second strategy six months later.

## Unmanaged Objects

Some PostgreSQL and MySQL objects cannot be expressed in TypeORM decorators:

- Extensions (`pg_trgm`, `uuid-ossp`, `pgcrypto`)
- Custom triggers and functions
- Materialized views
- Partial indexes with operator classes (`gin_trgm_ops`)
- Expression indexes (`CREATE INDEX ON x (lower(name))`)
- Row-level security policies
- Domain types and custom collations

For these, the migration SQL has no decorator counterpart. Add a leading comment to the migration file naming the bypass reason. If the project ships a TypeORM drift hook, set the bypass env var for that single tool call and revert it after.

## Verification (MANDATORY)

Before opening any PR that touches a migration file or an entity decorator:

```bash
# 1. Generate a probe migration against the current entity state.
# A zero-byte output (or one that contains only an empty class) means the
# entity and migration history agree. Any generated DDL is drift.
pnpm exec typeorm migration:generate \
  --dataSource src/data-source.ts \
  src/migrations/__probe__

# 2. Inspect the probe file. If it is non-empty, the schema and migrations
# are out of sync. Investigate and fix before pushing.

# 3. Discard the probe file.
rm -f src/migrations/__probe__-*.ts
```

A non-empty probe is a blocking issue.

## End-to-End Verification

When the change is non-trivial (new index, new column, new entity, new relation):

1. Spin up a fresh database: `docker compose -f docker-compose.test.yml up -d`.
2. Run all migrations: `pnpm exec typeorm migration:run --dataSource src/data-source.ts`.
3. Re-run the probe step above. If TypeORM generates DDL, the migration set is incomplete. Fix before pushing.
4. Run the full test suite. Any test that touches the changed entity must pass against the fresh schema.

## Down Migrations

Every migration must implement a working `down` method. TypeORM provides `migration:revert`, which calls `down` for the most recent migration. A no-op `down` is a defect.

| Operation | `down` must do |
|-----------|---------------|
| `ADD COLUMN` | `DROP COLUMN` |
| `DROP COLUMN` | `ADD COLUMN` with the original type, default, and nullability |
| `CREATE INDEX` | `DROP INDEX` with the same name |
| `CREATE TABLE` | `DROP TABLE` |
| Data migration | Reverse data transformation when reversible. When irreversible, document in the migration body and throw a clear error in `down` |

Migrations that perform irreversible data transformations (truncation, hash-based deduplication, lossy conversions) must throw in `down` with the message `Migration <name> is irreversible. Restore from backup.`. Silent no-op `down` methods break `migration:revert` semantics.

## Transactions

By default, TypeORM wraps each migration in a single transaction. For DDL that PostgreSQL cannot run inside a transaction (`CREATE INDEX CONCURRENTLY`, `ALTER TYPE ... ADD VALUE`, `VACUUM`), set the migration's `transaction = false` static field. Document the reason in a leading comment.

```typescript
export class AddTrgmIndex20260514120000 implements MigrationInterface {
  // CREATE INDEX CONCURRENTLY cannot run inside a transaction.
  public transaction = false;

  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      CREATE INDEX CONCURRENTLY IF NOT EXISTS "Game_search_trgm_idx"
      ON "game" USING gin ("homeTeam" gin_trgm_ops)
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX CONCURRENTLY IF EXISTS "Game_search_trgm_idx"`);
  }
}
```

## Schema Completeness

Every new entity must include these decorators and constraints before the PR is opened. Missing any of these is a review-blocking issue.

| Requirement | Rule |
|-------------|------|
| `createdAt` | `@CreateDateColumn()` on every entity |
| `updatedAt` | `@UpdateDateColumn()` on every entity that can be modified after creation. Append-only entities, like audit logs and event logs, are exempt |
| `deletedAt` | `@DeleteDateColumn()` when the entity participates in soft delete. Combine with `withDeleted: true` in queries that must include archived rows |
| `companyId` index | `@Index(['companyId'])` on every entity with a `companyId` column. Without it, every tenant-scoped query does a sequential scan |
| Compound indexes | `@Index(['companyId', 'status'])` and `@Index(['companyId', 'createdAt'])` when the entity is filtered by status or sorted by date |
| Foreign key indexes | TypeORM and PostgreSQL do not auto-create indexes on the owning side of foreign keys. Add `@Index` on every `@ManyToOne` join column unless it is already covered by a `@Unique` or `@PrimaryColumn` |
| Naming | Every `@Index`, `@Unique`, `@Check`, and `@ManyToOne` must pass an explicit `name` argument when the entity is not covered by a custom naming strategy |

When adding a new entity, run this checklist before committing:

1. Does it have `@CreateDateColumn` and `@UpdateDateColumn`?
2. Does it have `@Index(['companyId'])` if it has a `companyId` column?
3. Do all `@ManyToOne` relations have indexes on the join column?
4. Is the entity in the test cleanup order in `test/setup.ts`?
5. Does the seed file create records for this entity?
6. Does every `@Index`, `@Unique`, and `@Check` declaration include an explicit name?

## Service Layer Boundary

Routers, controllers, and API handlers must never import a `Repository<T>`, `EntityManager`, or `DataSource` directly. All database operations go through service classes. Inject the repository into the service via the DI container; the controller depends on the service interface, not on TypeORM.

A controller that imports `@InjectRepository` is a defect. Move the query into a service method. The same rule applies to test fixtures: setup helpers may inject repositories, but production code paths must not.

## Query Builder Over `query()`

Never call `queryRunner.query(...)`, `manager.query(...)`, `dataSource.query(...)`, or `repository.query(...)` from application code. These methods accept raw SQL strings, bypass the query builder's type system, skip TypeORM logging and subscribers, and break entity event hooks.

Acceptable uses of raw queries:

- Migration files, when the operation cannot be expressed with `queryRunner.createTable`, `queryRunner.createIndex`, etc.
- Operations that the query builder cannot express, like recursive CTEs or window functions. Wrap the raw call in a service method with a typed return signature, never in the calling code.
- Database-specific maintenance commands (`VACUUM`, `REINDEX`, `ANALYZE`) executed by an operational script.

Every raw query outside these scopes must be replaced with the equivalent query builder call or a typed repository method.

## Migration Ordering

When a project uses sequential migrations (`<timestamp>-<name>.ts`), migrations for the current task must always have the latest timestamps. Other team members may merge migrations while you work.

Before every commit, push, rebase, or PR:

1. List existing migrations: `ls src/migrations | sort | tail -5`.
2. If your migrations are not last, rename them with newer timestamps using `Date.now()` or the `migration:generate` clock.
3. Verify ordering again after rebase. Rebasing can interleave your migrations with newly merged ones, leaving them out of order.

## Idempotency

Every migration must be safe to run more than once. The migration log normally prevents re-execution, but partial failures, hand-edited `migrations` tables, and team errors all bypass it. Defend at the SQL level.

- `IF NOT EXISTS` on `CREATE TABLE`, `CREATE INDEX`, `CREATE EXTENSION`, `CREATE SCHEMA`, `CREATE TYPE`.
- `IF EXISTS` on every `DROP` statement.
- `DO $$ ... END $$` blocks with explicit existence checks for statements that lack a native `IF NOT EXISTS` clause (`CREATE MATERIALIZED VIEW`, `CREATE POLICY`, `CREATE TRIGGER` on some dialects).
- Never assume a clean slate. Another migration, a manual hotfix, or a partial deploy may have created the object already.

## Common Drift Sources

These patterns produce schema drift in TypeORM projects. Detect them in review.

| Pattern | Why it drifts |
|---------|--------------|
| `synchronize: true` in staging or production | TypeORM rewrites the schema on every entity change without logging the operation, leaving the migration history blank for those changes |
| Adding a column via direct SQL in production, then writing a `@Column` decorator without a matching migration | `migration:generate` produces a no-op next time the team runs it on a fresh database, then fails on a CI run that does have the column |
| Renaming a property in TypeScript without `name:` argument on the `@Column` decorator | Generates `DROP COLUMN <old>; ADD COLUMN <new>;` on the next migration, dropping the data |
| `@Index` declared without an explicit name on one developer's branch, with an explicit name on another's | Two migrations create different index names for the same logical index; both apply and one becomes orphaned |
| Mixing `@JoinColumn({ name: ... })` and `@RelationId` on the same relation | Generates conflicting foreign key constraints across migrations |

## Cross-References

- `~/.claude/rules/git-workflow.md` "Migration Ordering" and "Migration Idempotency" cover timestamp ordering and `IF NOT EXISTS` requirements.
- `~/.claude/rules/verification.md` "Database changes add" lists the verification gates.
- `~/.claude/checklists/checklist.md` category "Schema-Migration Sync" is the per-PR checklist.
- `~/.claude/rules/code-style.md` "No raw SQL" and "Service layer for data access" apply to TypeORM the same way they apply to Prisma.
- `~/.claude/rules/lang/prisma-migrations.md` is the parallel rule for Prisma; the conceptual structure is the same.

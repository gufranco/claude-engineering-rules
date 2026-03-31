# Database

## Schema Rules

- Always: `created_at`, `updated_at`
- Soft delete: `deleted_at` (nullable). In event-driven systems, publish a domain event on soft delete so downstream consumers can react. See `standards/distributed-systems.md` Saga Pattern for cross-service consistency
- Dates in UTC

## Query Optimization

- No `SELECT *`: specify columns
- No N+1: use include/eager loading, or batch loading (`WHERE id IN (...)`) for cases where eager loading causes cartesian explosion
- Pagination for lists
- Indexes for WHERE, JOIN, ORDER BY
- Filter at the database level, not in application code
- Use database-native aggregation instead of fetching rows and aggregating in the app

## Data Access Layer

- **Repository pattern**: data access functions return plain objects, never ORM-specific model instances. Use `raw: true`, `.lean()`, `toJSON()`, or equivalent to strip ORM metadata before returning data to the domain layer
- **Domain-ORM boundary**: the domain layer never imports or references the ORM, query builder, or database driver. It receives and returns plain data. This keeps business logic testable without a database and makes ORM migration feasible
- **Batch over iteration**: one query for N records beats N queries for 1 record. Use `WHERE id IN (...)`, bulk inserts, and batch updates. This applies to every I/O boundary: databases, APIs, file systems

## Isolation Levels

Choose the isolation level explicitly. The default varies by database and is often not what you need.

| Level | Prevents | Allows | When to use |
|-------|----------|--------|-------------|
| READ UNCOMMITTED | Nothing | Dirty reads, non-repeatable reads, phantoms | Almost never. Only for approximate analytics where stale data is acceptable |
| READ COMMITTED | Dirty reads | Non-repeatable reads, phantoms | Default for most OLTP workloads. Each statement sees only committed data |
| REPEATABLE READ | Dirty reads, non-repeatable reads | Phantoms (in some databases) | When a transaction must see a consistent snapshot for its duration. Reports, batch calculations |
| SERIALIZABLE | Everything | Nothing | Financial transactions, inventory where correctness is more important than throughput |

- **Default**: READ COMMITTED covers most cases. Only escalate when you have a specific correctness requirement.
- **Cost**: higher isolation = more locking = lower concurrency. SERIALIZABLE can cause significant contention under load.
- **Set explicitly**: `SET TRANSACTION ISOLATION LEVEL ...` or configure per connection/session. Never rely on the database default.

## Transactions and Atomic Writes

Multiple writes that must succeed or fail together require a transaction. No exceptions.

- Wrap related writes in a single transaction
- Keep transactions short: do validation and I/O before opening the transaction, not inside it
- Set an explicit statement timeout on long-running queries
- Handle transaction rollback explicitly on failure, do not rely on implicit cleanup
- For DynamoDB and similar: use `TransactWriteItems` for cross-item atomicity, or conditional expressions for single-item atomicity

### Conditional Writes

Prevent lost updates and race conditions by writing only when the current state matches expectations:

| Database | Pattern |
|----------|---------|
| SQL | `UPDATE ... WHERE version = :expected` (optimistic locking) |
| SQL | `INSERT ... ON CONFLICT DO NOTHING` (deduplication) |
| SQL | `SELECT ... FOR UPDATE` (pessimistic locking, use sparingly) |
| DynamoDB | `ConditionExpression: "attribute_not_exists(pk)"` (create-only) |
| DynamoDB | `ConditionExpression: "version = :expected"` (optimistic locking) |
| MongoDB | `findOneAndUpdate` with filter on version field |
| Redis | `WATCH/MULTI/EXEC` or Lua scripts for atomic read-modify-write |

When a conditional write fails, classify it: conflict (retry with fresh read) or duplicate (skip safely).

### ORM-Native Equivalents (Prisma)

When the project uses an ORM or query builder, never drop to raw SQL. No exceptions. In Prisma: never use `$executeRaw`, `$queryRaw`, or `$queryRawUnsafe`. Express every pattern through native methods:

| Raw SQL pattern | Prisma native equivalent |
|-----------------|--------------------------|
| `UPDATE ... WHERE version = :expected` (optimistic locking) | `update` with version field in `where`, handle `RecordNotFound` as conflict |
| `INSERT ... ON CONFLICT DO NOTHING` (deduplication) | `createMany` with `skipDuplicates: true`, or `upsert` |
| `SELECT ... FOR UPDATE` + conditional write | `updateMany` with full condition in `where`, check `count === 0` for conflict |
| `UPDATE ... WHERE condition` (atomic conditional) | `updateMany` with conditional `where`, check `count` for success/failure |
| Serializable isolation | `db.$transaction(fn, { isolationLevel: 'Serializable' })` |

**Default for atomic check-and-claim:** use `updateMany` with a conditional `where` clause. It translates to a single `UPDATE ... WHERE` at the database level. PostgreSQL's row-level lock during the UPDATE prevents concurrent transactions from seeing stale data. Reserve `Serializable` isolation for cases where multiple reads across different tables must be consistent within the same transaction.

## Access Pattern Design

Design the schema around how data will be queried, not just how it is structured.

1. List all access patterns before designing tables
2. For each pattern: what fields are queried, how are results sorted, what is the expected cardinality
3. Design keys, indexes, and partitions to serve those patterns without full scans
4. Document access patterns alongside the schema

### Time-Range Queries

Time-series data and date-range filtering need explicit design:

- **Partition by time period** (day, week, month) when the primary access pattern is "get data for date range"
- **Composite sort keys** with time component: `userId#2024-01-15` allows efficient range queries per user per date
- **Pre-aggregate** when the consumer needs summaries, not raw events. Store daily/hourly rollups alongside raw data
- **Avoid scanning when ranges cross partition boundaries**: if daily partitions are used but the query spans a month, the query must fan out across 30 partitions. Design partitions to match the most common query range

#### Timezone Alignment Trap

Daily partitions keyed on UTC date break when the consumer's "day" does not align with UTC boundaries. A user in UTC-5 asking for "Monday's data" needs records from Monday 05:00 UTC through Tuesday 04:59 UTC, spanning two UTC-day partitions.

**Always store raw events with UTC timestamps.** Then choose a query strategy:

| Strategy | When to use | How |
|----------|-------------|-----|
| Query-time boundaries | Default. User picks a date range, you compute UTC start/end | No daily partitions. Continuous timestamp index. Compute `start = localMidnight.toUTC()` and `end = nextLocalMidnight.toUTC()`, query with `BETWEEN` |
| Pre-aggregate per offset | Dashboards with fixed timezone per tenant, high read volume | Rollup rows keyed by `(offset, local_date)`. Write to the correct local-day bucket on ingestion |
| Overlapping fetch | Daily partitions already exist and cannot be changed | Fetch the two UTC days that overlap with the local day, filter the edges in the application |

**Default rule**: use query-time boundaries. Only pre-aggregate when you have measured that query-time computation is too slow for your volume. Never assume all consumers are in UTC.

### NoSQL Key Design

For DynamoDB, Cassandra, and similar:

- **Partition key**: high cardinality, even distribution. Never use a low-cardinality field (status, type) as the sole partition key
- **Sort key**: enables range queries within a partition. Use composite sort keys for hierarchical access (`type#timestamp`, `status#createdAt`)
- **GSI/LSI**: design for specific access patterns. Each index has cost: storage, write amplification, eventual consistency
- **Single-table design**: evaluate trade-offs. Reduces request count but increases query complexity. Use when access patterns are well-defined and stable
- **Avoid hot partitions**: distribute writes across partitions. Add a random suffix or use write sharding if one key receives disproportionate traffic

## Safe Migrations

### Mandatory Structure

Every migration must have both `up` and `down` functions. No exceptions.

- **`up`**: applies the change.
- **`down`**: reverts the change to the exact previous state. A `down` that drops a column must recreate it with the same type, default, constraints, and index. Nothing beyond the intended change may be lost.

### Atomicity

Wrap every migration in a transaction. A partial migration is worse than a failed one.

- If the ORM supports transactional migrations natively, use that mechanism.
- If the ORM does not, wrap the migration body in an explicit `BEGIN`/`COMMIT` with `ROLLBACK` on failure.
- Exception: operations that cannot run inside a transaction, like `CREATE INDEX CONCURRENTLY` in PostgreSQL. These must be the sole operation in the migration file and documented with a comment explaining why the transaction is absent.

### Data Preservation

A migration must not alter, drop, or modify anything beyond its stated intent. Before writing a migration:

1. Read the current schema for every table the migration touches.
2. Verify that the `down` function restores the schema to its exact prior state: columns, types, defaults, constraints, indexes, and comments.
3. If the migration removes a column or table, the `down` must recreate it with all original properties. If recreation is not feasible, like data loss on drop, document the limitation in a comment and require explicit confirmation before running.

### Operation Patterns

| Operation | Approach |
|-----------|----------|
| Add column | Nullable first, backfill, constraint |
| Remove column | Stop reading, deploy, remove |
| Rename column | Add new, copy, migrate code, remove old |
| Add index (manual/ad-hoc) | CONCURRENTLY |
| Add index (ORM migration) | Standard CREATE INDEX. ORMs like Prisma do not support CONCURRENTLY in their migration workflow. If zero-downtime is needed, create the index manually with CONCURRENTLY and mark the migration as applied |
| Change column type | Add new column, dual-write, migrate reads, drop old |
| Add NOT NULL | Add nullable, backfill, add constraint with NOT VALID, validate separately |

## Connection Management

- Use connection pooling. Never open a connection per request
- Set pool size based on expected concurrency, not a guess. Too large wastes resources, too small causes contention
- Configure idle timeout to reclaim unused connections
- Handle connection errors gracefully: retry on transient failures (deadlocks, lock timeouts), fail fast on auth errors. See `standards/resilience.md` for error classification and retry strategies
- For serverless: use a connection proxy (RDS Proxy, PgBouncer) to avoid connection exhaustion from cold starts

## Locking Strategy

- When the project has an ORM or query builder, use atomic conditional writes through native methods. In Prisma: `updateMany` with a conditional `where` clause. Never use raw `SELECT ... FOR UPDATE`
- `SELECT ... FOR UPDATE` is the correct database-level pattern for pessimistic locking in projects without an ORM or query builder
- Advisory locks (`pg_advisory_lock`) are aggressive: they block at the session or transaction level regardless of which rows are involved, causing performance problems under contention
- Only use advisory locks where provably necessary and where row-level locking is insufficient

## Production Safety

- Never run destructive operations (DELETE, TRUNCATE, DROP, schema changes) on production databases without explicit confirmation
- Use dev or test environments for experimentation and data exploration
- When modifying production data, always wrap in a transaction and verify before committing

## Naming

- Tables: `plural_snake_case`
- Columns: `singular_snake_case`
- FK: `<table>_id`
- Indexes: `idx_<table>_<columns>`
- Unique constraints: `uq_<table>_<columns>`

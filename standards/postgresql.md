# PostgreSQL

PostgreSQL-specific guidance. Generic database concerns live in [`database.md`](database.md).

## Connection Management

- Use a connection pool such as PgBouncer for transaction-mode pooling, or a driver-side pool like `pgx`, `node-postgres`, or `psycopg_pool`
- Cap pool size below the server's `max_connections` minus reserved superuser slots
- Set `idle_in_transaction_session_timeout` to bound runaway transactions (default: 60s for OLTP)
- Set `statement_timeout` per workload: short for HTTP handlers, longer for batch jobs
- Always close connections in `finally` blocks. Driver-level leaks block other tenants

## Transactions

- Default isolation: `READ COMMITTED`. Use `REPEATABLE READ` for multi-statement consistency, `SERIALIZABLE` only when correctness demands it. And accept the retry overhead
- Wrap all multi-statement business operations in a transaction. Single statements are auto-committed
- Use `SELECT ... FOR UPDATE` to lock rows for the rest of the transaction. Use `FOR UPDATE SKIP LOCKED` for queue-style consumers
- `SERIALIZABLE` transactions can fail with `serialization_failure (40001)`; the application must retry

## Indexes

- Use `CREATE INDEX CONCURRENTLY` on production tables to avoid blocking writes. The `migration-idempotency` hook enforces this
- Compound index column order: most selective first, then secondary filters, then sort columns
- Partial indexes, `WHERE` clause shrink size when most rows do not match
- Covering indexes, `INCLUDE` avoid heap lookups for index-only scans
- Drop unused indexes detected via `pg_stat_user_indexes`. `idx_scan = 0` for >30 days

## Vacuum and Bloat

- Autovacuum is on by default; tune `autovacuum_vacuum_scale_factor` to 0.05 for hot tables
- Run `VACUUM ANALYZE` after bulk loads
- Monitor bloat with `pgstattuple`. Above 30% bloat: consider `pg_repack`, online or `VACUUM FULL`. Locks
- High-churn tables benefit from `FILLFACTOR = 80-90` to leave HOT-update space

## JSONB

- Use `JSONB`, never `JSON`. JSONB is binary, indexable, and supports operators
- Index expressions used in WHERE: `CREATE INDEX ON t ((data->>'status'))`
- Use `GIN` indexes for full document search: `CREATE INDEX ON t USING gin (data jsonb_path_ops)`
- Validate shape at the application layer; PostgreSQL won't enforce JSONB schemas

## Replication and HA

- Streaming replication for read replicas. Promote with `pg_ctl promote` or your orchestrator
- Logical replication, publications, subscriptions when you need cross-version, cross-cluster, or selective replication
- Monitor replication lag with `pg_stat_replication.replay_lag`
- Synchronous replication for zero-data-loss but accept higher write latency

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| `SELECT *` in production code | Project the columns you need; reduces network and decoder overhead |
| Cursor-style pagination with OFFSET | Use keyset pagination (`WHERE id > :last_id`) for stable performance |
| `LIKE 'foo%'` without trigram extension | `CREATE EXTENSION pg_trgm` and use `gin_trgm_ops` |
| `now()` cached per transaction | Use `clock_timestamp()` for real-time stamps inside long transactions |
| Boolean columns nullable | Default to `NOT NULL DEFAULT false` unless three-state semantics are intended |

## Extensions

| Extension | Purpose |
|-----------|---------|
| `pg_stat_statements` | Query performance analytics. Enable in `shared_preload_libraries` |
| `pgcrypto` | UUIDs, hashing, symmetric encryption |
| `pg_trgm` | Trigram-based fuzzy search and indexes for `LIKE` |
| `btree_gin` | Combine GIN with btree-indexable columns |
| `pgaudit` | Compliance-grade auditing |
| `pg_repack` | Online table reorganization without long locks |

## PostgreSQL 18 Features

PostgreSQL 18 is the current major release. New surfaces worth adopting:

| Feature | Use |
|---------|-----|
| Native `uuidv7()` function | Generate timestamp-ordered UUIDs in SQL without a pgcrypto extension or application-side library. See [`identifiers.md`](identifiers.md) for the broader UUID v7 vs ULID decision |
| Virtual generated columns | Default behavior in 18. Computed at read time, no storage cost. Use for derived display columns that index lookups do not need |
| B-tree skip scan | The planner can now use multicolumn B-tree indexes even when the leading column is not in the `WHERE` clause. Reduces the number of single-purpose indexes needed |
| OAuth authentication | First-class OAuth in `pg_hba.conf`. Removes the need for a separate auth proxy when the IdP issues short-lived tokens |
| OLD and NEW in RETURNING | `RETURNING OLD.*, NEW.*` works on `INSERT`, `UPDATE`, `DELETE`, and `MERGE`. Removes a round-trip when the writer needs the prior state |
| Temporal constraints | Range types as the first argument of `PRIMARY KEY`, `UNIQUE`, and `FOREIGN KEY`. Use for slowly-changing dimensions, valid-time tables, and audit trails |
| Async I/O subsystem | Up to 3x faster sequential and bitmap heap scans without code changes. Confirm with `EXPLAIN (ANALYZE, BUFFERS)` before tuning further |

When the project is pinned to PG 16 or 17, document the constraint and the upgrade plan. Do not write code that depends on 18-only features without a planned migration path.

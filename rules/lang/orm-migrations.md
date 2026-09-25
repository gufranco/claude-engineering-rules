# ORM Migrations

Applies to Prisma, TypeORM, Drizzle, Sequelize, and MikroORM. The schema source is the single source of truth; every migration DDL has a matching schema declaration.

- Never use a schema-sync shortcut such as `db push`, `synchronize`, `sync()`, or `schema:update` outside local dev.
- Every index and constraint gets an explicit name: `<Table>_<col>_<purpose>_idx`.
- DDL is idempotent via `IF NOT EXISTS` and `IF EXISTS`; `CREATE INDEX CONCURRENTLY` gets its own migration.
- Your migrations sort last; no raw SQL outside migrations; handlers never import the ORM.
- Check drift with the ORM's diff or generate command before committing.

Full rule, per-ORM syntax, and rationale: [`standards/orm-migrations.md`](../../standards/orm-migrations.md). Read it before writing any migration or schema change.

## Enforcement

Enforced by: [`hooks/drizzle-raw-sql-blocker.py`](../../hooks/drizzle-raw-sql-blocker.py).
Enforced by: [`hooks/drizzle-schema-sync.py`](../../hooks/drizzle-schema-sync.py).
Enforced by: [`hooks/migration-idempotency.py`](../../hooks/migration-idempotency.py).
Enforced by: [`hooks/prisma-raw-sql-blocker.py`](../../hooks/prisma-raw-sql-blocker.py).
Enforced by: [`hooks/prisma-schema-sync.py`](../../hooks/prisma-schema-sync.py).
Enforced by: [`hooks/sequelize-raw-sql-blocker.py`](../../hooks/sequelize-raw-sql-blocker.py).
Enforced by: [`hooks/sequelize-schema-sync.py`](../../hooks/sequelize-schema-sync.py).
Enforced by: [`hooks/typeorm-raw-sql-blocker.py`](../../hooks/typeorm-raw-sql-blocker.py).
Enforced by: [`hooks/typeorm-schema-sync.py`](../../hooks/typeorm-schema-sync.py).

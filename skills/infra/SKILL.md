---
name: infra
description: Manage infrastructure for local development. Subcommands: docker, terraform, db. Covers container orchestration with Colima awareness, IaC workflows with safety gates, and database migrations with ORM detection. Use when user says "docker compose", "start containers", "terraform plan", "run migration", "create migration", "database setup", or needs to manage local dev infrastructure. Do NOT use for deploying to production (use CI/CD), security scanning (use /audit), or Terraform test patterns (check standards/terraform-testing.md).
sensitive: true
---
Unified infrastructure skill for local development. Replaces standalone `/docker`, `/terraform`, and `/db` skills.

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/infra` or `/infra docker` | Docker status and management (default) |
| `/infra terraform` | Terraform/OpenTofu workflows |
| `/infra db` | Database migrations and operations |

If no subcommand is given, default to `docker` (show status).

---

## docker

Manage Docker containers, compose services, and the runtime. Colima-aware, runtime-agnostic.

### Arguments

- No arguments or `status`: show status of all containers, compose services, runtime.
- `build [service]`: build images.
- `up [service]`: start services in detached mode.
- `down`: stop and remove compose containers (ask approval).
- `restart [service]`: restart services or standalone containers.
- `logs [service]`: show recent logs.
- `shell <service|container>`: interactive shell in a container.

### Steps

1. **Verify Docker and daemon.** `which docker`, `docker info`. If daemon not reachable:
   - Colima: check `colima status`, suggest `colima-start`.
   - Docker Desktop: suggest opening `/Applications/Docker.app`.
   - Linux: suggest `sudo systemctl start docker`.
2. **Detect runtime, compose, containers** (parallel): `docker context show`, resolve Docker context per `standards/borrow-restore.md`, find compose files, `docker ps -a`.
3. Execute the requested operation:
   - **status**: runtime info, compose services, all containers. Mention `lazydocker` if available.
   - **build**: `<compose> build [service]`. Mention `dive` for layer analysis.
   - **up**: `<compose> up -d [service]`. Verify with `<compose> ps`. Show logs of unhealthy services.
   - **down**: show services, ask approval, `<compose> down`.
   - **restart**: compose restart or `docker restart` for standalone. Verify health.
   - **logs**: `<compose> logs --tail=100` or `docker logs --tail=100`.
   - **shell**: find container, try bash, fall back to sh.

### Context Resolution

Never `docker context use`. Always `--context <name>` per command when project specifies `DOCKER_CONTEXT` or `DOCKER_HOST`.

### Standalone Containers

User has shell functions: `<service>-init`, `<service>-start`, `<service>-stop`, `<service>-purge`, `<service>-terminal`. Known services: mongo, postgres, redis, valkey, redict, ubuntu. Prefer suggesting these over raw docker commands.

---

## terraform

Run Terraform or OpenTofu with built-in safety checks. Always validate before plan, plan before apply.

### Arguments

- No arguments or `plan`: validate then plan.
- `init`: initialize working directory.
- `fmt`: format `.tf` files.
- `validate`: validate configuration.
- `apply`: validate, plan, show, apply after approval.
- `destroy`: plan destroy, show, destroy after approval.
- A directory path: use as working directory.

### Steps

1. **Detect tool and directory** (parallel): `which terraform`, `which tofu`. Check `.terraform-version`/`.opentofu-version`. Find `.tf` files.
2. **Check environment**: `.envrc` and direnv status. Show `TF_VAR_*`, `AWS_*` etc. (names only).
3. Check initialization (`.terraform` directory). Init if needed.
4. Execute:
   - **fmt**: `<tool> fmt -recursive -diff`, then apply.
   - **validate**: `<tool> validate`.
   - **plan**: validate first, then `<tool> plan -out=tfplan`. Summarize adds/changes/destroys.
   - **apply**: validate, plan, show summary, require approval, `<tool> apply tfplan`. Clean up plan file.
   - **destroy**: `<tool> plan -destroy -out=tfplan`, show what dies, require approval, apply.
5. Show workspace: `<tool> workspace show`.

### Rules

- Never assume terraform or tofu. Detect.
- Always validate before plan, plan before apply.
- Always require approval for apply and destroy.
- Always display current workspace.
- Never use `-auto-approve`.
- Never show secret values from env vars.

---

## db

Manage database migrations, containers, and data operations. Detects ORM and package manager automatically.

### Arguments

- No arguments: show migration status and container status.
- `migrate`: run pending migrations.
- `rollback`: rollback last batch (requires approval).
- `create <name>`: create new migration file.
- `seed`: run seeders.
- `reset`: rollback all and re-run (destructive, requires approval).
- `start`: start database container.
- `stop`: stop database container.
- `terminal`: open database shell.

### ORM Detection

`prisma/schema.prisma` = Prisma, `knexfile.*` = Knex, `sequelize` = Sequelize, `typeorm` + `data-source.*` = TypeORM, `drizzle.config.*` = Drizzle, `alembic.ini` = Alembic, `goose` = Goose, `diesel.toml` = Diesel.

### Steps

1. **Detect setup** (parallel): check Docker containers, resolve Docker context, detect ORM, detect package manager.
2. Execute:
   - **status**: container status (suggest shell functions if not running), migration status per ORM.
   - **start/stop**: suggest user shell functions (`postgres-start`, `mongo-start`, etc.).
   - **terminal**: suggest shell functions or direct exec (`docker exec -it postgres psql -U postgres`).
   - **migrate**: check container running, show pending, run ORM-specific migrate command, verify.
   - **rollback**: show status, warn about data loss, require approval, run ORM-specific rollback.
   - **create**: require name, run ORM-specific create command, show file path.
   - **seed**: run ORM-specific seed command.
   - **reset**: warn (destructive), require approval, rollback all, re-run all, verify.

### Standalone Container Details

Volumes: named Docker volumes + bind mounts to `~/Docker/<Service>/`. Ports bound to 127.0.0.1. Health checks built in. Credentials: postgres:postgres, mongo:mongo, redis no auth.

---

## Rules

- Always check Docker daemon before container commands.
- Suggest user shell functions over raw docker commands for standalone containers.
- Always detect compose files and commands. Never assume.
- Ask approval before `down`, `rollback`, `reset`, `destroy`.
- Never run `docker system prune` or `docker volume prune`.
- Never use `docker context use`. Always `--context <name>` per command.
- Never target a stopped Colima profile.
- Always detect ORM from project config.
- Check container running before migrations.
- Never run migrations against production.
- Never modify existing migration files.

## Related skills

- `/test` -- Run tests after migrations.
- `/ship` -- Commit infrastructure changes.
- `/audit docker` -- Dockerfile security checks.

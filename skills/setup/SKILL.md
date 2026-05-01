---
name: setup
description: Interactive project environment setup. Reads .env.example, prompts for missing values, detects required services and offers to start them via Docker, runs migrations, seeds the database, and verifies the app starts successfully. Use when user says "setup", "set up the project", "configure environment", "first time setup", "get this running", "initialize", or is setting up a project for the first time. Do NOT use for infrastructure management (use /infra), deployment (use /deploy), or README generation (use /readme).
sensitive: true
---
First-time project setup that detects the stack, installs dependencies, configures the environment, starts required services, runs database migrations and seeds, and verifies the application starts. Interactive: prompts for missing environment values and confirms before starting services.

## When to use

- When cloning a new project and setting it up for the first time.
- When onboarding to a project and the README setup steps are unclear or incomplete.
- When returning to a project after a long time and the environment may be stale.
- When a teammate asks "how do I get this running?"

## When NOT to use

- For managing production infrastructure. Use `/infra` instead.
- For deploying to staging or production. Use `/deploy` instead.
- For generating a README. Use `/readme` instead.
- For updating dependencies. Use `/audit deps` instead.

## Arguments

This skill takes no arguments. Run `/setup` and it walks through everything interactively.

## Steps

1. **Detect the project type.** Read the root directory for manifest files. Check for these in order:
   - `package.json`: Node.js project. Check for `pnpm-lock.yaml`, `yarn.lock`, or `package-lock.json` to determine the package manager.
   - `go.mod`: Go project.
   - `Cargo.toml`: Rust project.
   - `pyproject.toml` or `requirements.txt`: Python project.
   - `Makefile`: check for language-specific targets.
   - `docker-compose.yml` or `compose.yml`: containerized services.
   - If multiple manifest files exist, report all detected project types.

2. **Check prerequisites.** For each detected project type, verify the required runtime is installed. If `mise` is available (`which mise`) and the project has a `.mise.toml`, `.tool-versions`, `.node-version`, `.nvmrc`, `.python-version`, `.ruby-version`, or `.terraform-version` file, run `mise install` once to install every pinned runtime, then `mise current` to verify resolution. After that, the per-runtime checks below confirm the right version is active:
   - Node.js: `node --version`. Compare against `.node-version`, `.nvmrc`, `.tool-versions`, `.mise.toml`, or the `engines` field in `package.json`.
   - Go: `go version`. Compare against `.tool-versions` or `.mise.toml`.
   - Rust: `rustc --version` and `cargo --version`. Compare against `rust-toolchain.toml`.
   - Python: `python3 --version`. Compare against `.python-version`, `.tool-versions`, `.mise.toml`, or `pyproject.toml` requires-python.
   - Docker: `docker --version` and `docker compose version`.
   - If a prerequisite is missing and `mise` cannot resolve it, report it and stop. Do not install runtimes manually.

3. **Install dependencies.**
   - Node.js with pnpm: `pnpm install`.
   - Node.js with yarn: `yarn install`.
   - Node.js with npm: `npm ci`.
   - Go: `go mod download`.
   - Rust: `cargo build`.
   - Python with pip: `pip install -r requirements.txt` or `pip install -e .`.
   - Python with poetry: `poetry install`.
   - Report the result: success or failure with the error output.

4. **Environment setup.** Check for `.env.example` or `.env.template` in the project root.
   - If `.env` already exists, read it and compare against `.env.example`. List any variables present in the example but missing from `.env`.
   - If `.env` does not exist, copy `.env.example` to `.env`.
   - For each missing or placeholder variable, prompt the user:
     - Show the variable name.
     - Show the description from comments in `.env.example` if available.
     - Show the default value if one exists.
     - Ask for the value. Accept the default if the user presses enter.
   - Never overwrite values the user has already set in `.env`.

5. **Detect required services.** Scan these sources for service dependencies:
   - `docker-compose.yml` or `compose.yml`: list all services defined.
   - `.env.example`: look for connection strings or host variables that imply services: `DATABASE_URL`, `REDIS_URL`, `MONGODB_URI`, `ELASTICSEARCH_URL`, `RABBITMQ_URL`, `KAFKA_BROKERS`.
   - For each detected service, check if it is already running:
     - PostgreSQL: `pg_isready -h localhost` or check the port.
     - Redis: `redis-cli ping`.
     - MongoDB: `mongosh --eval "db.runCommand({ping:1})"` or check the port.
     - Docker services: `docker compose ps`.

6. **Offer to start services.** For each service that is not running:
   - If a docker-compose file defines the service, offer to start it: `docker compose up -d <service>`.
   - Wait for health checks to pass before proceeding. Use `docker compose ps` to verify the service reports as healthy.
   - If the service is not in docker-compose, inform the user that the service needs to be started manually and provide the typical connection details from the env vars.

7. **Run database setup.** Detect the ORM or migration tool:
   - Prisma: `npx prisma migrate dev` or `npx prisma db push` depending on the project stage. Then `npx prisma db seed` if a seed script exists.
   - Knex: `npx knex migrate:latest` then `npx knex seed:run` if seeds exist.
   - TypeORM: `npx typeorm migration:run`.
   - Django: `python manage.py migrate` then `python manage.py loaddata` if fixtures exist.
   - SQLAlchemy with Alembic: `alembic upgrade head`.
   - If no ORM is detected but `DATABASE_URL` exists, inform the user that manual database setup may be needed.

8. **Verify the application starts.** Detect the start command:
   - Node.js: check `package.json` scripts for `dev`, `start:dev`, or `start`.
   - Go: `go run .` or check a Makefile target.
   - Python: check for a `main.py`, `app.py`, or framework-specific entry point.
   - Start the application. Wait up to 15 seconds for a health check endpoint or for the process to stabilize.
   - If the app starts and responds to a health check, report success.
   - If the app crashes, capture the error output and report it with diagnostic suggestions.
   - Stop the application after verification. This is a setup check, not a long-running process.

9. **Present the setup report.**

   ```
   ## Setup Complete

   **Project:** <detected type and framework>
   **Runtime:** <version>
   **Package manager:** <name and version>

   ### Dependencies
   Installed successfully.

   ### Environment
   - .env created from .env.example
   - N variables configured

   ### Services
   | Service | Status |
   |---------|--------|
   | PostgreSQL | running on localhost:5432 |
   | Redis | running on localhost:6379 |

   ### Database
   - Migrations applied: N
   - Seed data loaded: yes/no

   ### Application
   Started successfully on http://localhost:3000

   ### Next steps
   - Run `pnpm dev` to start development
   - Run `pnpm test` to verify tests pass
   ```

## Rules

- Never overwrite an existing `.env` file. Merge missing values only.
- Always check if services are already running before attempting to start them. Starting a second instance on the same port causes errors.
- Always verify the application actually starts. "Dependencies installed" is not "setup complete."
- Never install runtimes or system-level tools automatically. Report what is missing and let the user decide how to install.
- When a step fails, report the error clearly and continue with the remaining steps where possible. A failed database migration should not prevent reporting what else was configured.
- Prefer `pnpm` for JavaScript and TypeScript projects. Only use `npm` or `yarn` when the lockfile indicates otherwise.
- When docker-compose starts a service, wait for its health check before running migrations. A started container is not a ready service.

## Related skills

- `/onboard` - Understand the codebase structure and architecture.
- `/infra` - Manage infrastructure for local development.
- `/health` - Check project quality after setup is complete.
- `/test` - Run the test suite to verify everything works.

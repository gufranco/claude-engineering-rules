---
name: onboard
description: Onboard to a new codebase with structured exploration. Scans the project, generates an architecture map with Mermaid diagrams, identifies entry points, explains the tech stack, lists key patterns and conventions, and produces a "start here" guide. Use when user says "onboard", "new project", "understand this codebase", "what does this project do", "walk me through the project", "project overview", or joins a new team or repository. Do NOT use for explaining a single file (use /explain), code review (use /review), or assessment (use /assessment).
---

Structured codebase exploration that produces a navigable architecture overview and a "Start Here" guide. Designed for the first hour on a new project.

## Arguments

- No arguments: scan the current working directory as the project root.
- `<path>`: use the specified path as the project root.

## Process

### Step 1: Detect the project

Read the manifest file to determine language, framework, and runtime version. Check in order: `package.json`, `go.mod`, `Cargo.toml`, `pyproject.toml`, `pom.xml`, `build.gradle`, `mix.exs`, `Gemfile`. Record:

- Language and version
- Framework and version
- Package manager
- Runtime constraints

### Step 2: Map directory structure

Run `ls` on the project root and each top-level directory. Classify each directory by purpose:

| Directory type | Examples |
|---------------|----------|
| Source code | `src/`, `lib/`, `app/`, `pkg/`, `internal/` |
| Tests | `test/`, `tests/`, `__tests__/`, `spec/` |
| Configuration | `config/`, `.github/`, `.husky/` |
| Build output | `dist/`, `build/`, `.next/`, `out/` |
| Documentation | `docs/`, `doc/` |
| Infrastructure | `infra/`, `terraform/`, `k8s/`, `docker/` |
| Database | `prisma/`, `migrations/`, `db/` |
| Scripts | `scripts/`, `bin/`, `tools/` |
| Static assets | `public/`, `static/`, `assets/` |

### Step 3: Identify entry points

Find the files where execution begins:

- `main` field in package.json
- Files named `main.ts`, `index.ts`, `app.ts`, `server.ts`, `main.go`, `main.rs`
- Route definitions: search for router setup, controller decorators, API route files
- CLI entry points: `bin` field in package.json, files with shebang lines
- Worker or job entry points: queue consumers, cron handlers

### Step 4: Read configuration

Read these files in parallel when they exist:

- TypeScript config: `tsconfig.json`
- Linter config: `.eslintrc*`, `biome.json`, `.prettierrc*`
- Docker: `Dockerfile`, `docker-compose.yml`
- CI: `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`
- Environment: `.env.example`
- Database: `prisma/schema.prisma`, migration files

### Step 5: Generate architecture diagram

Produce a Mermaid diagram showing:

- Modules and their responsibilities
- Dependencies between modules
- External services and integrations
- Data flow direction

Use `graph TD` for layered architectures, `graph LR` for pipeline architectures. Label edges with the type of interaction: HTTP, event, import, query.

### Step 6: Identify patterns

Search the codebase for structural patterns:

| Pattern | How to detect |
|---------|--------------|
| Repository | Files named `*.repository.ts`, `*.repo.go`, data access abstractions |
| Service layer | Files named `*.service.ts`, `*.svc.go`, business logic classes |
| Controller | Files named `*.controller.ts`, route handlers |
| Middleware | Files in `middleware/` directories, request interceptors |
| Event handlers | Files subscribing to events, queue consumers |
| State machines | Enum-based state transitions, status fields with defined flows |
| DTOs | Files named `*.dto.ts`, input/output shapes at boundaries |
| Guards/interceptors | Auth guards, validation interceptors, logging interceptors |

### Step 7: Read existing documentation

Read in parallel: `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `docs/` directory contents, `CLAUDE.md`. Note what is documented and what is missing.

### Step 8: Detect conventions

Identify the project's conventions by sampling 5-10 source files:

- Naming: camelCase vs snake_case, file naming patterns
- File structure: one export per file, barrel files, feature-based vs layer-based
- Test patterns: co-located tests vs separate test directory, naming convention
- Import style: relative vs absolute, path aliases
- Error handling: exceptions vs Result types, error classes

### Step 9: Output the Start Here guide

Produce a structured guide with these sections:

1. **What This Project Does**: one paragraph summary of the project's purpose
2. **Tech Stack**: language, framework, database, key dependencies
3. **Architecture**: the Mermaid diagram from Step 5 with a brief explanation
4. **Key Patterns**: list each pattern found in Step 6 with an example file
5. **How to Run**: commands to install, configure, and start the project
6. **How to Test**: test commands, test database setup, coverage commands
7. **Where to Start Reading**: the 3-5 most important files to read first, ordered
8. **Conventions to Follow**: the conventions detected in Step 8

### Step 10: Suggest next steps

Recommend running `/retro discover` to capture the detected conventions as durable rules in the project's configuration.

## Rules

- Never modify any project files during onboarding. This is a read-only exploration.
- Do not install dependencies or run build commands unless the user asks.
- When documentation is incomplete or contradicts the code, trust the code.
- Flag discrepancies between docs and code as findings.
- Keep the Start Here guide under 200 lines. Link to files instead of inlining code.

## Related skills

- `/explain` -- Deep explanation of a specific file or function.
- `/assessment` -- Full quality assessment of the codebase.
- `/retro discover` -- Capture conventions as rules.
- `/review` -- Review specific code changes.

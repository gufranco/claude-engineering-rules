# Twelve-Factor Application Design

Actionable rules for building cloud-native applications that deploy cleanly, scale horizontally, and run identically across environments. Each factor maps to specific practices with cross-references to deeper coverage in other standards.

## I. Codebase

One codebase tracked in version control, many deploys.

- One repo per application. Multiple codebases means a distributed system, not a single app
- Shared code between apps belongs in libraries managed through dependency managers, not copy-pasted
- Production, staging, and development are all deploys of the same codebase at different versions

See `rules/git-workflow.md` for branching, commits, and PR conventions.

## II. Dependencies

Explicitly declare and isolate all dependencies.

- Every dependency must appear in a manifest file (package.json, requirements.txt, go.mod, Cargo.toml). No implicit reliance on system-installed packages
- Use dependency isolation tools (node_modules, virtualenv, Go modules, containers) so no undeclared system dependency leaks in
- System tools like ImageMagick, ffmpeg, or curl must not be assumed available. If required, declare them in the Dockerfile or provision script, not just in documentation
- Declaration and isolation must be used together. One without the other is insufficient

See `rules/code-style.md` for version pinning and `rules/security.md` for supply chain security.

## III. Config

Store config in the environment. Strict separation between code and deploy-specific settings.

**Config is anything that varies between deploys:**

- Database URLs, cache hosts, queue endpoints
- Credentials for external services
- Per-deploy values: hostnames, ports, feature flags, log levels

**Config is NOT:**

- Internal wiring like route definitions, dependency injection setup, or framework configuration that stays the same across deploys. Those belong in code

**Rules:**

- Store config in environment variables. Not in code, not in checked-in config files
- Never group env vars into named environments (development, staging, production) inside the app. Each variable is independent and granular
- Validate all required env vars at startup. Fail fast with a clear message listing what is missing
- Document every env var in `.env.example` with placeholder values

See `rules/security.md` for secrets management.

## IV. Backing Services

Treat backing services as attached resources.

A backing service is any service consumed over the network: databases, caches, queues, SMTP servers, object storage, search indexes, monitoring APIs.

- The app makes no distinction between local and third-party services. A local PostgreSQL and an Amazon RDS instance are both just a `DATABASE_URL`
- Swapping a backing service requires only a config change, never a code change
- Each service instance is a distinct resource. Two PostgreSQL databases for different purposes are two resources with two URLs
- Resources can be attached and detached without code deploys. A failing database can be replaced with a restored backup by changing the URL

**Test implication:** development and test environments use the same backing service types as production. SQLite locally with PostgreSQL in production violates this factor.

See `standards/database.md` for connection management and `rules/testing.md` for real service requirements.

## V. Build, Release, Run

Strictly separate the three stages.

| Stage | What happens | Mutability |
|-------|-------------|------------|
| Build | Fetch dependencies, compile, produce artifact | Triggered by developer |
| Release | Combine build artifact with deploy-specific config | Immutable once created |
| Run | Execute the release in the target environment | Minimal moving parts |

- Code changes cannot happen at runtime. Every change requires a new build and release
- Every release has a unique identifier (Git SHA, timestamp, or incremental version)
- Releases are append-only. Rollback means deploying a previous release, not mutating the current one
- The run stage must be simple and predictable. Build complexity is acceptable because developers oversee it

See `standards/infrastructure.md` for CI/CD pipeline design and artifact management.

## VI. Processes

Execute the app as one or more stateless, share-nothing processes.

- Processes are stateless. Any data that needs to persist must live in a backing service (database, cache, object store)
- Local memory and filesystem are single-transaction scratch space only. Never assume cached data or temp files survive the next request
- **No sticky sessions.** Session data belongs in a time-expiring external store (Redis, Memcached), not in process memory. Sticky sessions prevent horizontal scaling and make deployments fragile
- Asset compilation and preprocessing happen during the build stage, not at runtime

See `standards/distributed-systems.md` for stateless service design and `standards/caching.md` for external cache strategies.

## VII. Port Binding

Export services via port binding. The app is completely self-contained.

- The application binds to a port and listens for requests. It does not rely on an external webserver container (Apache, Tomcat) injected at runtime
- A webserver library is a dependency declared in the manifest (Express, Uvicorn, Gin, Actix), not an external runtime
- In development: `http://localhost:$PORT`. In production: a routing layer (load balancer, reverse proxy) maps public hostnames to the port-bound process
- This applies beyond HTTP. Any protocol (gRPC, WebSocket, AMQP) is exported by binding to a port. For gRPC, bind the gRPC server to its own port. For WebSocket, bind on the same HTTP port with an upgrade path, or on a separate port if the transport layer requires it. For SSE, use the HTTP port with proper connection draining on shutdown
- One port-bound app can become a backing service for another by providing its URL through config

## VIII. Concurrency

Scale out via the process model.

- Processes are first-class citizens. Assign different work types to different process types: web processes handle HTTP, worker processes handle background jobs, scheduler processes handle cron
- Scale horizontally by running more processes of each type, not by making individual processes larger
- Never daemonize processes or write PID files. Delegate process lifecycle to the platform (systemd, Kubernetes, container orchestrator)
- Internal concurrency (threads, async I/O, goroutines) is fine within a process but is not a substitute for the process model. A single process with 100 threads cannot scale across machines

See `standards/infrastructure.md` for HPA, autoscaling, and process orchestration.

## IX. Disposability

Maximize robustness with fast startup and graceful shutdown.

**Fast startup:**

- Minimize startup time to seconds. Fast startup enables rapid scaling, deployment, and process relocation
- If initialization is expensive (loading ML models, warming caches, running migrations), do it in the build or release stage, not at process start

**Graceful shutdown:**

- Handle SIGTERM by stopping new work, completing in-flight requests, then exiting
- Web processes: stop accepting connections, finish current requests (with a timeout), close cleanly
- Worker processes: return the current job to the queue (NACK, release lock) before exiting. The job will be picked up by another worker

**Crash resilience:**

- Design for sudden, ungraceful death. Hardware fails. OOM kills happen. The app must not corrupt data when this occurs
- All jobs must be reentrant: wrapped in transactions or designed to be idempotent. A job interrupted halfway through and retried must produce the correct result
- Use crash-only design as a mental model: if the only way to stop the app is to crash it, and it still works correctly, the design is sound

**Container signal handling:**

- A process running as PID 1 in a container does not receive default signal handlers from the kernel. SIGTERM, SIGHUP, and other signals may be silently dropped
- Use an init process like `tini` or `dumb-init` as the container entrypoint. It forwards signals correctly and reaps zombie child processes
- In Dockerfiles: `ENTRYPOINT ["/sbin/tini", "--"]` followed by `CMD ["your-app"]`. Alternatively, use `docker run --init`

See `standards/distributed-systems.md` for graceful shutdown and `standards/resilience.md` for idempotency patterns.

## X. Dev/Prod Parity

Keep development, staging, and production as similar as possible.

**Three gaps to minimize:**

| Gap | Traditional | Twelve-Factor |
|-----|------------|---------------|
| Time | Weeks between code and deploy | Hours or minutes |
| Personnel | Devs write, ops deploy | Same people do both |
| Tools | SQLite locally, PostgreSQL in production | Same backing services everywhere |

- Use the same type and version of every backing service across all environments. Containers make this practical and cheap
- "Lightweight local substitutes" (SQLite for PostgreSQL, in-memory cache for Redis, local filesystem for S3) create subtle incompatibilities that only surface in production. Avoid them
- Modern tools (Docker, docker-compose, devcontainers) eliminate the cost argument for running production-equivalent services locally

See `standards/infrastructure.md` for environment parity and module-based provisioning.

## XI. Logs

Treat logs as event streams.

- The app writes to stdout (info, debug) and stderr (errors, warnings). It never manages log files, rotation, or routing
- One event per line, unbuffered, as structured JSON
- The execution environment (container runtime, log collector, systemd) captures, collates, and routes streams to their final destination
- The app is unaware of its log destination. The same code works in a terminal, Docker, and Kubernetes without changes

See `standards/observability.md` for structured logging, log levels, sensitive data masking, and correlation IDs.

## XII. Admin Processes

Run admin and management tasks as one-off processes.

**Common admin tasks:**

- Database migrations
- REPL/console sessions for debugging
- One-time data fixes or backfill scripts

**Rules:**

- Admin processes run against the same release (code + config) as the app's long-running processes. A migration script must use the same database URL, the same ORM version, and the same connection settings as the web process
- Admin code ships with the application repository, not in separate scripts or repos. This prevents version drift between the admin task and the app it operates on
- Admin processes use the same dependency isolation as the app. If the web process runs in a container, the migration runs in the same container image
- In production, run admin tasks via the platform's one-off process mechanism (Kubernetes Job, ECS RunTask, Heroku one-off dyno, SSH + exec), not by modifying running processes

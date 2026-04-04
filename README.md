<div align="center">

<strong>Ship code that passes review the first time. 25 rules, 51 on-demand standards, 30 skills, 42 MCP servers, 15 runtime hooks, and 24 custom agents that turn Claude Code into an opinionated engineering partner.</strong>

<br>
<br>

[![CI](https://img.shields.io/github/actions/workflow/status/gufranco/claude-engineering-rules/ci.yml?style=flat-square&label=CI)](https://github.com/gufranco/claude-engineering-rules/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/gufranco/claude-engineering-rules?style=flat-square)](LICENSE)

</div>

---

**25** rules · **51** standards · **30** skills · **42** MCP servers · **15** hooks · **24** agents · **629** checklist items · **57** categories · **~15,000** lines of engineering standards

<table>
<tr>
<td width="50%" valign="top">

### Runtime Guardrails

Fifteen hooks intercept tool calls in real time: block dangerous commands, scan for secrets, enforce conventional commits, prevent large file commits, guard environment files, enforce multi-account token safety for `gh` and `glab`, auto-format code, track every file change, send webhook notifications, preserve context across compaction, and log tool failures.

</td>
<td width="50%" valign="top">

### Two-Tier Rule Loading

Universal rules load automatically. Domain-specific standards load on demand, matched by trigger keywords from `rules/index.yml`. Cuts auto-loaded context from ~135KB to ~50KB per conversation.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Slash-Command Skills

`/ship`, `/review`, `/test`, `/audit`, `/plan`, `/infra`, and 6 more. 25 workflows consolidated into 30 skills with subcommands. Each skill orchestrates multi-step workflows with a single command.

</td>
<td width="50%" valign="top">

### Anti-Hallucination by Design

Mandatory verification gates, pre-flight checks, response self-check for analytical output, prompt injection guards on skills that process external content, and a "never guess" policy. Every file path, import, and API call must be verified before use.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 629-Item Review Checklist

Single unified checklist spanning 57 categories, from correctness and security to distributed systems, deployment verification, design quality, LLM trust boundary, performance budgets, zero-downtime deployment, supply chain security, and event-driven architecture. Shared by completion gates, `/review`, and `/assessment`.

</td>
<td width="50%" valign="top">

### Clean Room Verification

30+ checks across seven sections prevent plagiarism when using external projects as reference. Structural, naming, logic, license, and documentation independence gates with similarity thresholds.

</td>
</tr>
</table>

## The Problem

Claude Code is capable out of the box, but it does not enforce your engineering standards. It will happily mock your database in tests, commit with vague messages, skip CI checks, guess import paths, and write code that passes locally but fails in review. Every conversation starts from zero, with no memory of how your team works.

## The Solution

This configuration turns Claude Code into an opinionated engineering partner. Rules define what it should do. Hooks enforce it at runtime. Skills automate the tedious parts. Standards load on demand so context stays small.

| Capability | Vanilla Claude Code | With This Config |
|:-----------|:-------------------:|:----------------:|
| Conventional commits enforced | - | Yes |
| Secret scanning before commit | - | Yes |
| Dangerous command blocking | - | Yes |
| Multi-account token safety | - | Yes |
| Integration-first test policy | - | Yes |
| Pre-flight verification gates | - | Yes |
| On-demand domain standards | - | Yes |
| 16 workflow skills (25 absorbed) | - | Yes |
| 42 MCP server integrations | - | Yes |
| Prompt injection guards | - | Yes |
| 629-item review checklist (57 categories) | - | Yes |
| Clean room plagiarism prevention | - | Yes |

## How It Works

This repository configures Claude Code's global behavior through `~/.claude/`. Three mechanisms work together:

```mermaid
graph LR
    subgraph Input
        A[User Command]
    end
    subgraph PreToolUse Hooks
        B[Dangerous Command Blocker]
        C[Secret Scanner]
        D[Conventional Commits]
        B2[GH Token Guard]
        B3[GLab Token Guard]
        E2[Large File Blocker]
        F2[Env File Guard]
    end
    subgraph Claude Code
        E[CLAUDE.md Rules]
        F[Domain Rules]
        G[Skills]
    end
    subgraph PostToolUse Hooks
        H[Smart Formatter]
        I[Change Tracker]
    end
    A --> B & C & D & B2 & B3 & E2 & F2
    B & C & D & B2 & B3 & E2 & F2 --> E
    E --> F
    F --> G
    G --> H & I
```

**Rules** define what Claude should do. **Hooks** enforce it at runtime. **Skills** automate multi-step workflows.

## What's Included

### Rules (always loaded)

These 25 rules are loaded into every conversation automatically.

| Rule | What it covers |
|:-----|:---------------|
| `code-style` | DRY/SOLID/KISS, immutability, data safety gates, error classification, discriminated unions, branded types, typed error returns, total functions, TypeScript conventions |
| `testing` | Integration-first philosophy, strict mock policy, AAA pattern, fake data generators, deterministic tests |
| `security` | Secrets management, auth checklist, encryption, data privacy, audit logging, supply chain security |
| `code-review` | PR authoring, review style, test evidence, branch freshness, documentation checks, tech debt tracking |
| `git-workflow` | Conventional commits, branch naming, local quality gate before commit/push, CI monitoring, PR creation, conflict resolution, rollback strategy |
| `debugging` | Four-phase process: reproduce, isolate, root cause, fix+verify. Multi-component tracing |
| `verification` | Evidence-based completion gates, response self-check for analytical output, no claim without fresh evidence |
| `writing-precision` | Precision gate for all text output: concrete over abstract, examples over vague instructions, self-test before finalizing |
| `pre-flight` | Duplicate check, market research, architecture fit, interface verification, root cause confirmation, scope agreement |
| `documentation` | Preserve existing valid information when skills modify documentation files. Content migration verification for file consolidations |
| `language` | Response language enforcement. All output in English regardless of user input language |
| `github-accounts` | Multi-account safety for `gh` CLI: require inline `GH_TOKEN`, block `gh auth switch`, account mapping by remote URL |
| `gitlab-accounts` | Multi-account safety for `glab` CLI: require inline `GITLAB_TOKEN` and `GITLAB_HOST`, block `glab auth login` |
| `agent-usage` | Agent and parallelism budget: inline-first policy, two-agent concurrency cap, cascade prevention, context injection rules, result size management |
| `clean-room` | Clean room implementation: 30+ verification checks across structural, naming, logic, config, license, documentation, and output independence. Similarity thresholds, safe/unsafe boundaries, per-source process |
| `context-management` | Context compaction at 60%, preservation rules after compaction, plan re-reading every ~50 tool calls, subagent context isolation |
| `ai-guardrails` | Treat AI output as junior dev code, plan before generating, multi-agent validation, never commit unexplainable code, track AI-specific defect rates |
| `changelog` | User-facing changelog entries, lead with what users can do, separate internal changes, version tagging convention |
| `hook-authoring` | Hook performance budget under 500ms, exit codes, stdin JSON parsing, testing with fixtures, graceful error handling |
| `skill-authoring` | Skill frontmatter fields, allowed-tools scoping, sensitive flag, preamble pattern, context fork, supporting file conventions |
| `mcp-security` | MCP server scoping to specific agents, credential isolation, output shape validation, 5-6 active server limit for performance |
| `performance` | Core Web Vitals budgets, API latency targets (p50/p95/p99), database query time limits, JS/CSS bundle size limits, image optimization |
| `privacy` | Data minimization, retention policies with automated deletion, right to erasure, consent recording, pseudonymization, audit trail |
| `session-hygiene` | Session naming with `-n`, checkpoint before risky operations, `/rewind` as save points, multi-session awareness, proactive compaction |
| `cost-awareness` | Token cost estimation before agent spawning, model tier selection (Haiku for read-only), redundant read avoidance, CI pipeline cost awareness |

### Standards (loaded on demand)

These 51 standards live in `standards/` and are loaded only when the task matches their domain. `rules/index.yml` maps each standard to trigger keywords for automatic matching.

| Standard | What it covers |
|:---------|:---------------|
| `infrastructure` | IaC principles, networking, container orchestration, CI/CD pipeline design, cloud architecture, DORA metrics |
| `distributed-systems` | Consistency models, saga pattern, outbox, distributed locking, event ordering, schema evolution, zero-downtime deploys |
| `frontend` | Typography, spacing, WCAG AA contrast, responsive design, accessibility, component patterns, performance |
| `resilience` | Error classification, retries with backoff, idempotency, deduplication, DLQs, circuit breakers, back pressure |
| `database` | Schema rules, query optimization, isolation levels, safe migrations, conditional writes, NoSQL key design |
| `observability` | Structured logging, metrics naming, distributed tracing, health checks, SLIs/SLOs, alerting, incident response |
| `llm-docs` | LLM-optimized documentation URLs for 64 technologies. Fetch before coding, never guess APIs |
| `api-design` | REST conventions, error format, pagination, versioning, deprecation lifecycle, rate limiting, bulk operations |
| `borrow-restore` | Safe global state management for CLI tools: Docker contexts, gh accounts, terraform workspaces |
| `caching` | Cache-aside/write-through strategies, invalidation, thundering herd prevention, cache warming, sizing |
| `cost-optimization` | Cost allocation tagging, compute right-sizing, storage lifecycle policies, network cost reduction, database cost tuning, budget alerts, FinOps practices |
| `identifiers` | Identifier type selection: UUID v1-v8, ULID, TSID, Snowflake, TypeID, CUID2, NanoID, xid, Sqids. Decision flowchart, use-case matrix, DB storage, index performance |
| `twelve-factor` | Cloud-native app design: stateless processes, config in env, backing services, disposability, admin processes |
| `hexagonal-architecture` | Ports and adapters: port interfaces, adapter implementations, dependency direction, per-layer testing |
| `railway-oriented-programming` | Result type composition: map, flatMap, error accumulation, neverthrow, Effect, boundary conversion |
| `ddd-tactical-patterns` | Entities, value objects, aggregates, domain events, repositories, domain services, ubiquitous language |
| `state-machines` | Type state pattern, runtime state machines, transition tables, guard conditions, XState, testing strategies |
| `accessibility-testing` | WCAG AA/AAA compliance, axe-core integration, Lighthouse CI, Pa11y, manual testing checklist, ARIA patterns, color contrast verification |
| `algorithmic-complexity` | Data structure selection guide, sorting algorithm comparison, complexity analysis rules, anti-pattern catalog, space complexity |
| `multi-tenancy` | Tenant isolation strategies, noisy neighbor prevention, data leakage prevention with RLS, tenant-scoped observability, tenant lifecycle, cross-tenant testing, per-tenant configuration |
| `graphql-api-design` | Schema design, query complexity limits, N+1 prevention with DataLoader, error unions, field-level auth, federation, subscriptions, persisted queries, schema evolution |
| `websocket-realtime` | WebSocket and SSE lifecycle, reconnection with backoff, message envelopes, sequence ordering, deduplication, backpressure, horizontal scaling with pub/sub, security hardening |
| `message-queues` | Queue topology patterns, message envelopes with schema versioning, consumer groups, ordering guarantees, DLQ and poison message handling, exactly-once processing, monitoring and lag alerts, platform comparison |
| `feature-flags` | Flag types and lifecycle, evaluation performance with local cache, rollout strategies with automatic rollback, flag cleanup and expiration, testing both states, boundary evaluation pattern, observability, platform comparison |
| `browser-testing` | Playwright test architecture, page objects, visual regression, accessibility tree testing, responsive testing, Core Web Vitals measurement, cookie management |
| `terraform-testing` | Terraform built-in test framework with .tftest.hcl files, plan vs apply mode, mock providers, parallel execution, state key isolation |
| `grpc-services` | gRPC service design, proto file conventions, error handling with status codes, deadlines, interceptors, health checking, load balancing |
| `i18n-l10n` | Text externalization, pluralization with ICU MessageFormat, number/date/currency formatting, RTL support, locale detection, translation workflow |
| `data-pipelines` | Batch, micro-batch, and streaming pipelines, idempotent processing, backfill strategy, data quality validation, ETL vs ELT |
| `mlops` | Model lifecycle, experiment tracking, feature stores, model serving patterns, data and concept drift detection |
| `ab-testing` | Experiment design, statistical rigor, power analysis, assignment and randomization, multivariate testing, analysis methodology |
| `mobile-development` | Framework selection, navigation, offline support, performance optimization, push notifications, app store compliance |
| `dashboard-design` | Purpose-driven dashboards, layout principles, metric grouping with RED method, SLO visualization, chart selection |
| `documentation-generation` | OpenAPI generation from code, AsyncAPI for events, GraphQL schema docs, TypeDoc, documentation-as-code, CI validation |
| `event-driven-architecture` | CQRS, event sourcing, outbox pattern, saga choreography and orchestration, event versioning, idempotent handlers, partition key strategy, DLQ routing |
| `authentication` | OAuth 2.1 with PKCE, passkeys/FIDO2, token lifecycle, NIST 800-63B passwords, MFA, session management, auth rate limits |
| `monorepo` | pnpm workspaces, Turborepo/Nx task orchestration, workspace protocol, changeset versioning, per-package builds, cache targets |
| `contract-testing` | Consumer-driven contracts with Pact, can-i-deploy CI gate, provider verification, contract versioning |
| `sre-practices` | SLIs from real user metrics, SLOs as operational targets, error budgets, burn rate alerts, change freeze policy, postmortem cadence |
| `performance-budgets` | Core Web Vitals targets, resource budgets for JS/CSS/images, CI alerts at 80% threshold, code splitting, fetchpriority |
| `zero-downtime-deployments` | Blue-green, canary, rolling strategies, expand-contract database migrations, progressive delivery with feature flags |
| `secrets-management` | Dynamic secrets with TTL rotation, External Secrets Operator for K8s, secret scanning, rotation automation, emergency revocation |
| `container-security` | Non-root containers, minimal base images, multi-stage builds, no secrets in layers, image scanning, SLSA provenance, cosign |
| `opentelemetry` | SDK init order, semantic conventions, composite sampling, Collector deployment, trace-log correlation, W3C Trace Context |
| `privacy-engineering` | Pseudonymization, data retention automation, right to erasure, consent management, dark pattern avoidance, privacy impact assessment |
| `serverless-edge` | Stateless design, cold start optimization, concurrency limits, edge functions for auth/routing/geo, timeout budgets |
| `api-gateway` | Gateway vs BFF decision framework, cross-cutting concerns at gateway, protocol translation, circuit breaking at gateway level |
| `strangler-fig` | Incremental legacy migration through facade/proxy, request routing by migration status, data consistency during transition |
| `typescript-5x` | using/await using for resource management, NoInfer, verbatimModuleSyntax, regex syntax checking, inferred type predicates |

### Skills

30 skills with subcommands, consolidating 25+ workflows.

| Skill | Subcommands | What it does |
|:------|:------------|:-------------|
| `/ship` | `commit`, `pr`, `release`, `checks`, `worktree` | Full delivery pipeline: semantic commits, PRs with CI monitoring, tagged releases, pipeline diagnosis, parallel worktrees. Auto-checks documentation staleness on PR creation |
| `/deploy` | `land` (default), `canary` | Post-merge deployment: merge PR, verify deployment health, canary monitoring for errors and regressions |
| `/review` | `code` (default), `qa`, `design` | Three-pass code review with 57-category checklist, 30-rule QA analysis with PICT and coverage delta, visual/UX/accessibility audit with 0-10 dimension scoring |
| `/audit` | `deps`, `secrets`, `docker`, `code`, `scan`, `image`, `threat` | Multi-layer security audit, dependency management with trivy/snyk/gitleaks, STRIDE threat modeling |
| `/test` | `perf`, `lint`, `scan`, `ci`, `stubs` | Test execution, load testing (k6/wrk/hey/ab), coverage, linting, security scanning, test stub generation |
| `/plan` | `adr`, `scaffold` | Structured planning with spec folders, discovery phase (`--discover`), automated multi-phase review (`--auto`), Architecture Decision Records, boilerplate generation |
| `/investigate` | `--freeze`, `--unfreeze` | Systematic debugging with hypothesis testing, 3-strike limit, optional directory-level edit freeze |
| `/design` | `consult` (default), `variants`, `system` | Design consultation, variant exploration, design system scaffolding. Produces DESIGN.md before implementation |
| `/second-opinion` | `--mode gate/adversarial/consult` | Cross-model code review via Ollama (local), OpenAI, or other providers. Catches single-model blind spots |
| `/infra` | `docker`, `terraform`, `db` | Container orchestration (Colima-aware), IaC workflows with safety gates, database migrations with ORM detection |
| `/retro` | `discover`, `--curate`, `--promote` | Session retrospective, codebase pattern extraction, memory curation, rule graduation (self-improving agent lifecycle) |
| `/assessment` | -- | Architecture completeness audit against the full 57-category checklist |
| `/morning` | -- | Start-of-day dashboard: open PRs, pending reviews, notifications, standup prep |
| `/incident` | -- | Incident context gathering and blameless postmortem generation |
| `/readme` | -- | README generation by analyzing the actual codebase |
| `/palette` | -- | Accessible OKLCH color palette generation for Tailwind CSS and shadcn/ui |
| `/checkpoint` | `save`, `resume`, `list` | Save and resume working state across sessions: git state, decisions, remaining work |
| `/health` | -- | Code quality dashboard: typecheck + lint + test + coverage + dead code, weighted 0-10 score with trends |
| `/fix-issue` | `<number>` | Fix a GitHub issue by number: fetch, analyze, search codebase, implement with tests, commit referencing the issue |
| `/learn` | `show`, `search`, `add`, `prune`, `export`, `stats` | Operational learnings manager: confidence-scored, decaying insights across sessions |
| `/guard` | `<directory>`, `off` | Combined safety: directory freeze + destructive command warnings + scope enforcement |
| `/cso` | `daily` (default), `comprehensive` | Chief Security Officer: OWASP Top 10, STRIDE threat modeling, secrets archaeology, supply chain audit |
| `/benchmark` | `api`, `bundle`, `--save` | Performance regression detection: API latency, bundle size, query time with baselines |
| `/pr-summary` | `<number>` | PR summary with reviewer suggestions based on file ownership from git history |
| `/document-release` | -- | Post-ship documentation sync: finds stale, missing, or outdated docs relative to the latest diff |
| `/explain` | `<path>`, `--depth shallow\|deep` | Code explanation with Mermaid diagrams, data flow tracing, pattern identification |
| `/session-log` | `export` | Session activity logger: files changed, tests run, commits made, decisions taken |
| `/migrate` | `<from> <to>` | Framework/library migration: detect usage, plan migration, apply incrementally with testing |
| `/office-hours` | -- | Pre-code brainstorming: 6 forcing questions, produces design document, no code |
| `/canary` | `<duration>`, `<url>` | Post-deploy monitoring: HTTP checks every 30s, compare against baseline, suggest rollback |

### Hooks

#### Global hooks (active in all projects)

| Hook | Trigger | What it does |
|:-----|:--------|:-------------|
| `dangerous-command-blocker.py` | PreToolUse (Bash) | Three-level protection across 14 categories: filesystem destruction, privilege escalation, reverse shells, git destructive, AWS/GCP/Azure cloud CLI, platform CLI (Vercel/Netlify/Firebase/Cloudflare/Fly.io/Heroku), Docker/Podman/Kubernetes/Helm, database CLI (Redis/MongoDB/PostgreSQL/MySQL/SQLite), IaC (Terraform/OpenTofu/Pulumi/Ansible/CDK/Serverless), SQL statements, secret exfiltration via commands, cron/systemd, and protected branch pushes |
| `secret-scanner.py` | PreToolUse (Bash) | Scans staged files for 30+ secret patterns before any git commit |
| `conventional-commits.sh` | PreToolUse (Bash) | Validates commit messages match conventional commit format |
| `gh-token-guard.py` | PreToolUse (Bash) | Blocks `gh` commands without inline `GH_TOKEN` and blocks `gh auth switch` to prevent global account mutation |
| `glab-token-guard.py` | PreToolUse (Bash) | Blocks `glab` commands without inline `GITLAB_TOKEN` and blocks `glab auth login` to prevent global config mutation |
| `large-file-blocker.sh` | PreToolUse (Bash) | Blocks commits containing files over 5MB to prevent accidental binary commits |
| `env-file-guard.sh` | PreToolUse (Write/Edit/MultiEdit) | Blocks modifications to `.env` files, private keys (.pem, .key, id_rsa, id_ed25519), cloud credentials (.aws/credentials, .docker/config.json, .kube/config), package manager auth (.npmrc, .pypirc, .netrc), Terraform state (.tfstate, .tfvars), GCP service account JSON, SSH/GPG directories, and secrets/credentials directories |
| `smart-formatter.sh` | PostToolUse (Edit/Write/MultiEdit) | Auto-formats files by extension using prettier, black, gofmt, rustfmt, rubocop, or shfmt |
| `change-tracker.sh` | PostToolUse (Edit/Write/MultiEdit) | Logs every file modification with timestamps, auto-rotates at 2000 lines |
| `deslop-checker.sh` | PostToolUse (Edit/Write/MultiEdit) | Warns on AI-generated code patterns: narration comments, debug artifacts, empty catches, boolean literal comparisons, contextless TODOs. Never blocks, only warns |
| `notify-webhook.sh` | Stop | Sends a POST to `CLAUDE_NOTIFY_WEBHOOK` when a response completes. Slack and Discord compatible. Silent no-op if env var is unset |
| `compact-context-saver.sh` | PreCompact/PostCompact | Saves git status before compaction, restores it after. Prevents context loss across compaction events |
| `failure-logger.py` | PostToolUseFailure | Logs failed tool calls to `~/.claude/telemetry/failures.jsonl` with timestamp, tool name, error, and file path |

#### Per-project hooks (opt-in)

| Hook | Trigger | What it does |
|:-----|:--------|:-------------|
| `scope-guard.sh` | Stop | Compares modified files against spec scope, warns on scope creep. Supports freeze mode (`~/.claude/.freeze-scope`) for directory-level edit restrictions during debugging |
| `tdd-gate.sh` | PreToolUse (Edit/Write) | Blocks production code edits if no corresponding test file exists |

### Custom Agents

Specialized subagents in `agents/` handle recurring analysis tasks. Each agent follows the template in `agents/TEMPLATE.md` with standardized sections: identity, constraints, process, output contract, scenario handling, and final checklist.

| Agent | Model | Purpose |
|:------|:------|:--------|
| `blast-radius` | Haiku | Trace all consumers of changed interfaces to identify the full impact of a code change |
| `code-simplifier` | Haiku | Detect AI-generated code patterns and suggest cleanups |
| `coverage-analyzer` | Sonnet | Analyze test coverage gaps on changed files and generate missing test scenarios |
| `dependency-analyzer` | Sonnet | Compare packages in a category using maintenance, community, security, size, and API quality criteria |
| `migration-planner` | Haiku | Verify database migrations for idempotency, reversibility, ordering, and data loss risks |
| `security-scanner` | Sonnet | Scan code for security vulnerabilities, secret leaks, and supply chain issues |
| `test-scenario-generator` | Sonnet | Generate structured test scenarios with priority classification and requirement traceability |
| `red-team` | Sonnet | Adversarial analysis: attack happy paths under load, exploit trust assumptions, find silent failures |
| `api-reviewer` | Sonnet | API backward compatibility and design review: response shapes, status codes, naming, pagination |
| `performance-profiler` | Sonnet | Performance hotspot analysis: N+1 queries, missing indexes, unbounded loops, O(n^2) patterns |
| `accessibility-auditor` | Sonnet | Accessibility review: keyboard navigation, ARIA patterns, color contrast, focus management, alt text |
| `pr-reviewer` | Sonnet | Confidence-scored PR review with AUTO-FIX/ASK disposition heuristic, JSON output |
| `documentation-checker` | Haiku | Documentation accuracy: README vs code, stale links, env var coverage, API doc drift |
| `scope-drift-detector` | Haiku | Compare current diff against plan.md to detect unplanned scope expansion |
| `i18n-validator` | Haiku | Translation file validation: missing keys, diacritical marks, interpolation mismatches, locale coverage |

To create a new agent, copy `agents/TEMPLATE.md` and fill in each section. Key design rules from `rules/agent-usage.md`: agents must not spawn subagents, must specify exact output format, and must include a final checklist.

### Decision Trailers

Commit messages support optional trailers that record decision context. Validated by `conventional-commits.sh` when present.

| Trailer | Format | Purpose |
|:--------|:-------|:--------|
| `Rejected` | `Rejected: <alternative> \| <reason>` | Documents a rejected approach with the reason |
| `Constraint` | `Constraint: <description>` | Records a constraint that shaped the decision |
| `Risk` | `Risk: <description>` | Flags a known risk introduced by the change |

See `rules/git-workflow.md` "Decision Trailers" section for the full specification and examples.

### Context Snapshots

The `/plan` skill writes a `context.md` file in the spec folder before planning begins. This snapshot captures: task statement, desired outcome, known facts, constraints, unknowns, codebase touchpoints, and branch state. The snapshot is re-read at the start of each planning phase to prevent context drift in long sessions.

### Rule Index

`rules/index.yml` is the catalog for both tiers. It maps each rule and standard to a description and trigger keywords. When a task starts, Claude matches the task against trigger keywords and reads the relevant `standards/` files on demand. Skills like `/plan` and `/retro discover` also reference this index. Run `/retro discover` to add project-specific entries.

### Checklist

One unified checklist covers all layers of quality:

- **Unified checklist** (`checklists/checklist.md`): 629 items across 57 categories. Single source of truth shared by completion gates (self-review during implementation), `/review`, and `/assessment`. Categories 1-17 cover code-level quality: correctness, security, error handling, concurrency, data integrity, algorithmic performance, frontend performance, testing, code quality and design, naming, architecture patterns, backward compatibility, dependencies, documentation, cross-file consistency, cascading fix analysis, and zero warnings. Categories 18-49 cover architecture and infrastructure: idempotency, atomicity, error classification, caching, consistency models, back pressure, saga coordination, event ordering, schema evolution, observability, security, API design, deployment readiness, graceful degradation, data modeling, capacity planning, testability, cost awareness, multi-tenancy, migration strategy, infrastructure as code, networking, container orchestration, CI/CD, and cloud architecture. Category 50 covers clean room verification. Category 51 covers deployment verification. Category 52 covers design quality. Category 53 covers LLM trust boundary: output validation before storage, sanitization for vector DBs, URL allowlisting. Category 54 covers performance budgets: Core Web Vitals targets, bundle sizes, image dimensions. Category 55 covers zero-downtime deployment: expand-contract migrations, backward compatibility, canary verification. Category 56 covers supply chain security: SBOM generation, artifact signing, lockfile integrity, typosquatting prevention. Category 57 covers event-driven architecture: idempotent handlers, event deduplication, schema versioning, DLQ routing.

## Workflows

Step-by-step guides for every engineering scenario. Each workflow shows which skills, rules, and agents are involved.

### 1. New Feature: From Idea to Production

**When:** you receive a feature request, ticket, or decide to build something new.

```
/plan --discover "add user notifications with email and push"
```

1. **Discovery.** `/plan --discover` asks 6 forcing questions: what problem, who is the user, what does success look like, minimum scope, risks, and alternatives considered. Answers go into `specs/<date>-<slug>/decisions.md`.

2. **Research.** The plan skill searches the codebase, open PRs, closed PRs, and branches for existing solutions. It also searches for community packages that already solve the problem. Findings go into `references.md`.

3. **Plan.** The skill evaluates 2-3 approaches with trade-offs, creates a spec folder with `plan.md`, `decisions.md`, `references.md`, and `context.md`. Review the plan before proceeding.

4. **Scaffold.** If the feature needs new files:
   ```
   /plan scaffold service notification
   /plan scaffold endpoint notifications
   ```
   This reads 2-3 existing examples of the same type, matches naming, export style, imports, and generates skeleton files with `TODO` placeholders.

5. **Implement.** Follow the spec's task breakdown. After each meaningful change, verify it works:
   ```
   /test
   ```

6. **Test coverage.** Verify 95%+ coverage on all changed and related files:
   ```
   /test --coverage
   ```

7. **QA analysis.** Map all behavior paths and find coverage gaps:
   ```
   /review qa --fix
   ```
   The `--fix` flag auto-generates missing tests after presenting the analysis.

8. **Self-review.** Catch issues before anyone else sees the code:
   ```
   /review --local
   ```
   This runs the full 57-category checklist against your local changes, including blast radius analysis on consumers of changed interfaces.

9. **Commit and push.**
   ```
   /ship commit --push --pipeline
   ```
   Groups changes into logical commits, pushes, and monitors CI until all checks pass. Diagnoses and fixes failures automatically (max 3 retry cycles).

10. **Create PR.**
    ```
    /ship pr
    ```
    Generates a structured PR description (What/How/Testing), checks for stale documentation, and monitors the pipeline.

11. **Deploy.** After PR approval:
    ```
    /deploy land
    /deploy canary
    ```
    Merges the PR, waits for deployment, then monitors the live app for 10 minutes checking for console errors and performance regressions.

**Rules involved:** `pre-flight.md`, `code-style.md`, `testing.md`, `git-workflow.md`, `verification.md`
**Agents used:** `coverage-analyzer`, `blast-radius`, `test-scenario-generator`

### 2. Bug Fix: From Report to Resolution

**When:** a bug is reported, a test fails, or you notice unexpected behavior.

```
/investigate "users receive duplicate notifications after password reset"
```

1. **Reproduce.** `/investigate` starts the four-phase debugging process. It asks you to reproduce the bug reliably. If it is intermittent, it looks for timing, concurrency, or state dependencies.

2. **Isolate.** The skill performs binary search: comments out halves of the system until the failure disappears. Checks `git log` for recent changes, uses `git bisect` if the bug exists on a branch but not on main.

3. **Root cause.** State a hypothesis, predict what a test input will produce, run it. If the prediction is wrong, discard the theory entirely. The 3-strike protocol applies: after 3 failed fix attempts, the skill escalates with a structured summary of what was tried.

4. **Freeze scope (optional).** To prevent accidentally modifying unrelated files during debugging:
   ```
   /investigate --freeze
   ```
   This restricts edits to the module under investigation. Run `/investigate --unfreeze` when done.

5. **Test first.** Write a test that fails due to the bug:
   ```
   /test src/notifications/notification.service.test.ts
   ```

6. **Fix.** Address the root cause, not the symptom. One change at a time.

7. **Verify.** Run the full test suite, not just the fixed test:
   ```
   /test
   ```

8. **Ship.**
   ```
   /ship commit --push --pipeline
   ```
   The commit message references the fix: `fix(notifications): prevent duplicate sends on password reset`.

**Rules involved:** `debugging.md` (four phases + 3-strike protocol), `testing.md`, `verification.md`

### 3. Code Review: Reviewing Someone Else's PR

**When:** you are asked to review a pull request.

```
/review 142
```

1. **Scope detection.** The review skill categorizes the diff into scope signals (SCOPE_FRONTEND, SCOPE_BACKEND, SCOPE_AUTH, SCOPE_MIGRATIONS, etc.) to prioritize which specialist checks to apply.

2. **Standard loading.** Based on the project's technology stack and the diff content, the skill loads relevant standards from `index.yml`. A PR that adds a database migration loads `standards/database.md` and `standards/zero-downtime-deployments.md`.

3. **Blast radius.** For every changed interface, the skill traces all consumers in the project. A changed function signature that has 40 callers is flagged if callers were not updated.

4. **Three-pass review.** Pass 1: per-file analysis against all 57 checklist categories. Pass 2: cross-file consistency. Pass 3: cascading fix analysis for every issue found.

5. **Confidence scoring.** Each finding gets a confidence score 1-10. Findings below 5 are suppressed. Findings 5-6 show with a caveat.

6. **Verdict.** APPROVE, REQUEST_CHANGES, or COMMENT with blast radius summary and list of standards applied.

7. **Post comments.** After your review, post inline comments directly to the PR:
   ```
   /review 142 --post
   ```

**For large PRs**, focus on one area:
```
/review 142 --backend
/review 142 --frontend
```

**Rules involved:** all 25 rules loaded, all matched standards from `index.yml`
**Agents used:** `blast-radius`, `pr-reviewer`, `performance-profiler` (if SCOPE_BACKEND), `accessibility-auditor` (if SCOPE_FRONTEND)

### 4. Self-Review: Checking Your Own Code Before Delivery

**When:** you finished implementing and want to verify quality before creating a PR.

```
/review --local
```

1. This reviews your local branch diff against the base branch using the same 57-category checklist as a PR review.

2. The fix-first heuristic classifies findings as AUTO-FIX (dead code, N+1, stale comments) or ASK (security, design decisions). AUTO-FIX issues are fixed directly.

3. After fixing, run QA analysis to verify test coverage:
   ```
   /review qa
   ```

4. For frontend changes, add a design audit:
   ```
   /review design
   ```
   This checks typography, color contrast, spacing, responsiveness, accessibility, and AI-pattern detection with 0-10 dimension scoring.

### 5. Full Application Assessment

**When:** you want to audit the entire implementation for architectural completeness, before an interview submission, or before declaring a project production-ready.

```
/assessment
```

1. **Requirement gathering.** The skill searches the entire project for requirement documents (README, INSTRUCTIONS, BRIEF, ASSIGNMENT) and asks if you have additional context from email, job postings, or external sources.

2. **Company research (interview context).** If you provide a company name, it searches their engineering blog, GitHub org, tech talks, and Glassdoor interview reviews to understand what patterns they value.

3. **Build verification.** Runs build, lint, typecheck, and tests with coverage. A failing build is CRITICAL.

4. **Planted defect hunting.** Reads the code with suspicion, looking for intentional bugs and anti-patterns.

5. **Technology discovery.** Scans the project for technology signals and loads all matching standards from `index.yml`. A project using PostgreSQL + GraphQL + Redis loads `database.md`, `graphql-api-design.md`, and `redis.md`.

6. **57-category audit.** Every applicable category is checked. Findings are classified as PRESENT, PARTIAL, or MISSING with severity (CRITICAL/HIGH/MEDIUM/LOW) and effort (S/M/L/XL).

7. **Fix and converge.** After presenting findings: "Want me to implement the missing patterns?" The skill fixes issues by priority (CRITICAL first), re-verifies after each batch, and loops up to 20 iterations until clean.

**Focus areas for targeted assessment:**
```
/assessment --focus security
/assessment --focus resilience
/assessment --focus api
/assessment --focus frontend
/assessment --focus events
/assessment --focus auth
/assessment --focus deploy
```

**Rules involved:** all 25 rules, all matched standards, full 57-category checklist
**Agents used:** `security-scanner`, `coverage-analyzer`, `red-team`, `documentation-checker`

### 6. Debugging: Systematic Investigation

**When:** something is broken and you need to find the root cause.

```
/investigate "API returns 500 on POST /orders when items array has more than 50 elements"
```

The skill follows `rules/debugging.md` four-phase process with the 3-strike error protocol:

1. **Reproduce.** Find the minimal reproduction case. Record exact input, environment, and steps.

2. **Isolate.** Binary search the problem space. Check `git log --oneline -20` and `git diff HEAD~5`. If the bug exists on a branch but not on main, use `git bisect`.

3. **Root cause.** Explain WHY, not WHERE. Predict what a specific input will do, run it, compare. Wrong prediction means wrong theory: discard it entirely and start fresh.

4. **Fix and verify.** One change at a time. Write a test that fails without the fix and passes with it. Run the full test suite.

**Strike protocol:**
- Strike 1: diagnose the error, apply a targeted fix
- Strike 2: same error? Try a completely different approach
- Strike 3: question the assumptions. Search docs and community
- After 3 strikes: escalate with a structured summary of all attempts

**CI-only failures:**
```
/ship checks
```
Fetches failed CI logs, diagnoses each failure, and suggests fixes. Use when the issue manifests in CI but passes locally.

### 7. Architecture Planning

**When:** starting a project, planning a major feature, or making a significant technical decision.

```
/plan --discover --auto "migrate authentication from sessions to JWT with refresh tokens"
```

1. **Discovery.** `--discover` runs 6 forcing questions before any planning starts.

2. **Scope review.** `--auto` challenges the scope with four lenses: expansion (what is missing), selective expansion (best ROI additions), hold (is scope right), reduction (what can be cut).

3. **Research.** Searches codebase, PRs, branches, and community packages for existing solutions.

4. **Alternatives.** Evaluates 2-3 approaches with trade-offs, decisive tests, stop signals, and pivot triggers.

5. **Spec folder.** Creates `specs/<date>-<slug>/` with `plan.md`, `decisions.md`, `references.md`, and `context.md`.

**Record architecture decisions:**
```
/plan adr new "Replace session store with JWT"
```
Creates an ADR in `docs/adr/` documenting context, decision, alternatives, and consequences.

**Generate boilerplate from existing patterns:**
```
/plan scaffold service payment
/plan scaffold endpoint invoices
/plan scaffold component DataTable
```

### 8. Daily Routine

**When:** starting your workday.

```
/morning
```

1. **Open PRs.** Shows your open PRs with CI status and review state.
2. **Pending reviews.** Lists PRs waiting for your review, sorted by age.
3. **Notifications.** GitHub and GitLab notifications summary.
4. **Standup prep.** Summarizes what you did yesterday based on commits and PR activity.

**Jump straight into reviews:**
```
/morning --review
```
Reviews pending PRs smallest-first, one by one.

**End of day:**
```
/retro
```
Captures corrections, preferences, and patterns from the session as durable configuration updates.

### 9. Security Audit

**When:** before a release, after adding dependencies, or as a periodic check.

```
/audit
```

Runs all layers: dependencies, secrets, Docker, code patterns, and deep scanning. Findings are prioritized by severity.

**Targeted audits:**

| Command | What it checks |
|:--------|:---------------|
| `/audit deps` | Known vulnerabilities in dependencies |
| `/audit deps outdated` | Packages with available updates |
| `/audit deps update lodash` | Update a specific package with verification |
| `/audit secrets` | Secrets in code and git history |
| `/audit docker` | Dockerfile security best practices |
| `/audit code` | Code patterns: injection, XSS, SSRF |
| `/audit scan` | Deep scan with trivy/snyk/gitleaks |
| `/audit image myapp:latest` | Docker image vulnerability analysis |
| `/audit threat` | STRIDE threat modeling |

**Rules involved:** `security.md` (OAuth 2.1, passkeys, NIST 800-63B, secrets management, supply chain)
**Agents used:** `security-scanner`, `red-team`

### 10. Dependency Management

**When:** updating packages, evaluating new dependencies, or responding to vulnerability alerts.

1. **Check vulnerabilities:**
   ```
   /audit deps
   ```

2. **Check for outdated packages:**
   ```
   /audit deps outdated
   ```

3. **Update a specific package:**
   ```
   /audit deps update express
   ```
   Runs tests after the update, verifies no breakage.

4. **Evaluate a new package before adding:**
   Ask Claude to compare options. The `dependency-analyzer` agent compares the top 3-5 packages in a category using maintenance activity, community size, vulnerabilities, bundle size, and API quality.

### 11. Release

**When:** all planned changes are merged to main and you are ready to cut a release.

```
/ship release --dry-run
```

Preview the release first. The skill detects the version bump from commit types: `BREAKING CHANGE` or `!` bumps major, `feat` bumps minor, `fix`/`perf` bumps patch.

```
/ship release
```

Tags the release, generates a changelog grouped by type (Features, Bug Fixes, Performance, Breaking Changes), and creates a GitHub/GitLab release.

### 12. Infrastructure Operations

**When:** managing Docker containers, Terraform resources, or database migrations.

**Docker:**
```
/infra docker
```
Shows container status. Detects Colima profiles. Uses per-command `--context` flags to avoid polluting global Docker state.

**Terraform:**
```
/infra terraform
```
Validates before planning, plans before applying. Requires explicit approval before any apply or destroy. Never auto-approves.

**Database migrations:**
```
/infra db
```
Detects your ORM (Prisma, Knex, TypeORM). Runs migrations, manages database containers, handles seed data.

### 13. Design Consultation

**When:** starting a new UI, exploring visual approaches, or building a design system.

**Consultation with research:**
```
/design consult "admin dashboard for order management"
```
Researches similar designs, proposes component hierarchy, color palette, typography, spacing, and produces `DESIGN.md`.

**Compare multiple approaches:**
```
/design variants
```
Generates 3-5 visual approaches with trade-offs for accessibility, performance, and complexity.

**Scaffold a design system:**
```
/design system
```

### 14. Cross-Model Code Review

**When:** you want an independent perspective from a different AI model.

```
/second-opinion --mode gate
```

| Mode | What it does |
|:-----|:-------------|
| `gate` | Pass/fail decision. Binary quality check |
| `adversarial` | Actively tries to break the code. Finds edge cases |
| `consult` | Open-ended discussion about the approach |

Uses Ollama (local, no API key needed) by default. Also supports OpenAI and other providers. Findings from both models are cross-referenced: overlapping issues have high confidence, unique issues per model warrant investigation.

### 15. Incident Response

**When:** a production incident occurs and you need to document it.

```
/incident
```

Gathers incident context: error logs, timeline, affected systems. Generates a blameless postmortem following the template in `standards/observability.md`: summary, impact, timeline, root cause, contributing factors, action items with owners.

### 16. Parallel Development with Worktrees

**When:** you need to work on multiple tasks simultaneously without branch switching.

```
/ship worktree init "fix auth bug | add notification feature | update docs"
```

Creates three isolated worktrees, each with its own branch. Work in any of them without affecting the others.

**Ship from a worktree:**
```
/ship worktree deliver
```
Commits, pushes, and creates a PR from the current worktree.

**Check status of all worktrees:**
```
/ship worktree check
```

**Clean up merged worktrees:**
```
/ship worktree cleanup
```

### 17. Establishing Project Standards

**When:** joining a new project and want to capture its conventions, or when a project has matured and patterns should be codified.

1. **Discover existing patterns:**
   ```
   /retro discover
   ```
   Scans the codebase for recurring patterns: naming conventions, file structure, error handling style, test patterns. For each pattern found, the skill asks why it exists and creates a rule after your confirmation.

2. **Focus on a specific area:**
   ```
   /retro discover --area src/api
   ```

3. **Write to project-level config instead of global:**
   ```
   /retro discover --output project
   ```

4. **Clean up stale memory:**
   ```
   /retro --curate
   ```

5. **Graduate useful patterns to rules:**
   ```
   /retro --promote
   ```

### 18. CI Pipeline Diagnosis

**When:** CI fails and you need to understand why.

```
/ship checks
```

Fetches failed job logs from GitHub Actions or GitLab CI, diagnoses each failure with the error, relevant log excerpt, and suggested fix. Searches for existing fixes in the source branch, open PRs, and remote branches before suggesting new ones.

```
/ship checks 142
```
Check a specific PR by number.

### 19. Color Palette Generation

**When:** starting a frontend project and need an accessible color system.

```
/palette
```

Generates an OKLCH color palette with WCAG AA contrast verification, ready for Tailwind CSS and shadcn/ui. Outputs CSS custom properties and Tailwind config values.

### 20. README Generation

**When:** the project needs a professional README.

```
/readme
```

Scans the entire project: code structure, dependencies, infrastructure, CI/CD, environment variables, scripts, license, and visual assets. Generates a README with hero section, metrics bar, feature grid, architecture diagram, quick start, and project structure.

### 21. Test Execution and Load Testing

**When:** running tests, checking coverage, or load testing an endpoint.

| Command | What it does |
|:--------|:-------------|
| `/test` | Run the full test suite |
| `/test src/api` | Run tests matching a path |
| `/test --coverage` | Run with coverage reporting, verify 95%+ |
| `/test --watch` | Run in watch mode during development |
| `/test lint` | Run linters |
| `/test scan` | Security vulnerability scanning |
| `/test ci` | Simulate CI locally with `act` |
| `/test perf https://localhost:3000/api/users` | Load test an endpoint with k6/wrk/hey |
| `/test stubs src/services/payment.service.ts` | Generate test stubs for uncovered code |

### 22. Post-Deploy Verification

**When:** code has been deployed and you want to verify it is working.

```
/deploy canary
```

Monitors the live application for a configurable duration:
- Checks for new console errors
- Compares error rate against pre-deploy baseline
- Monitors performance metrics against baseline
- Suggests rollback if regression detected

### Workflow Decision Guide

Not sure which workflow to use? Find your scenario:

| Scenario | Start with |
|:---------|:-----------|
| "I need to build X" | Workflow 1: New Feature |
| "Something is broken" | Workflow 2: Bug Fix |
| "Can you review this PR?" | Workflow 3: Code Review |
| "Is my code ready to ship?" | Workflow 4: Self-Review |
| "Is this project production-ready?" | Workflow 5: Full Assessment |
| "Why is this failing?" | Workflow 6: Debugging |
| "How should I implement this?" | Workflow 7: Architecture Planning |
| "What do I do first today?" | Workflow 8: Daily Routine |
| "Are we secure?" | Workflow 9: Security Audit |
| "Any vulnerable dependencies?" | Workflow 10: Dependency Management |
| "Time to release" | Workflow 11: Release |
| "Need to manage Docker/Terraform/DB" | Workflow 12: Infrastructure |
| "Need a UI design" | Workflow 13: Design Consultation |
| "Want a second opinion" | Workflow 14: Cross-Model Review |
| "Production is down" | Workflow 15: Incident Response |
| "Need to work on 3 things at once" | Workflow 16: Parallel Development |
| "New project, need to set standards" | Workflow 17: Project Standards |
| "CI is failing" | Workflow 18: Pipeline Diagnosis |
| "Need a color palette" | Workflow 19: Color Palette |
| "README is outdated" | Workflow 20: README Generation |
| "Run tests or load test" | Workflow 21: Test Execution |
| "Just deployed, is it working?" | Workflow 22: Post-Deploy |

## Quick Start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Claude Code | Latest | [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |
| Git | >= 2.0 | Pre-installed on macOS |
| Python 3 | >= 3.8 | Pre-installed on macOS |

### Setup

```bash
git clone git@github.com:gufranco/claude-engineering-rules.git
```

Symlink or copy the contents into `~/.claude/`:

```bash
# Option A: symlink (recommended, stays in sync with git)
ln -sf "$(pwd)/claude-engineering-rules/"* ~/.claude/

# Option B: copy
cp -r claude-engineering-rules/* ~/.claude/
```

### Verify

Open Claude Code in any project and run:

```bash
/ship commit
# Should enforce conventional commit format
```

The hooks, rules, and skills activate automatically.

<details>
<summary><strong>Project structure</strong></summary>

```
~/.claude/
  CLAUDE.md              # Core engineering rules (~255 lines)
  settings.json          # Permissions, hooks, MCP servers, statusline
  .markdownlint.json     # Markdownlint configuration for CI
  checklists/
    checklist.md         # 629-item unified checklist across 57 categories
  rules/                 # Tier 1: always loaded into every conversation (25 rules)
    index.yml            # Rule catalog with trigger keywords for both tiers
    agent-usage.md       # Agent parallelism budget and cascade prevention
    clean-room.md        # Clean room implementation and plagiarism prevention
    code-review.md       # PR authoring, review style, tech debt
    code-style.md        # DRY/SOLID, immutability, FP patterns, TypeScript conventions
    debugging.md         # Four-phase debugging process
    documentation.md     # Documentation preservation during skill execution
    git-workflow.md      # Commits, branches, CI, PRs
    github-accounts.md   # GitHub multi-account safety
    gitlab-accounts.md   # GitLab multi-account safety
    language.md          # Response language enforcement
    pre-flight.md        # Pre-implementation verification gates
    security.md          # Secrets, auth, encryption, supply chain
    testing.md           # Integration-first, strict mocks, fake data, snapshots
    verification.md      # Evidence-based completion gates
    writing-precision.md # Precision gate for all text output
    context-management.md # Context compaction and preservation
    ai-guardrails.md     # AI output review and trust boundaries
    changelog.md         # Changelog writing standards
    hook-authoring.md    # Hook performance and testing conventions
    skill-authoring.md   # Skill frontmatter and structure conventions
    mcp-security.md      # MCP server scoping and credential isolation
    performance.md       # Core Web Vitals and API latency budgets
    privacy.md           # Data minimization, retention, erasure
    session-hygiene.md   # Session naming, checkpoints, multi-session
    cost-awareness.md    # Token cost, model selection, CI cost
  standards/             # Tier 2: loaded on demand when task matches triggers
    accessibility-testing.md   # WCAG compliance, axe-core, Lighthouse, ARIA, contrast
    algorithmic-complexity.md  # Data structures, sorting, anti-patterns, space complexity
    api-design.md        # REST conventions, pagination, versioning
    borrow-restore.md    # CLI context management pattern
    caching.md           # Strategies, invalidation, thundering herd
    cost-optimization.md # Cost allocation, right-sizing, lifecycle policies, FinOps
    database.md          # Schema, queries, migrations, locking
    ddd-tactical-patterns.md   # DDD tactical patterns
    distributed-systems.md # Consistency, saga, outbox, locking, events
    frontend.md          # Typography, a11y, responsive, components
    hexagonal-architecture.md  # Ports and adapters pattern
    identifiers.md       # Identifier type selection guide and decision framework
    infrastructure.md    # IaC, networking, containers, CI/CD, cloud
    llm-docs.md          # LLM-optimized doc URLs for 64 technologies
    multi-tenancy.md     # Tenant isolation, noisy neighbor, data leakage, lifecycle
    observability.md     # Logging, metrics, tracing, SLOs, incidents
    railway-oriented-programming.md  # Result type composition
    resilience.md        # Retries, idempotency, DLQs, back pressure
    state-machines.md    # Type state and runtime state machines
    twelve-factor.md     # Cloud-native app design across all 12 factors
    graphql-api-design.md # GraphQL schema, complexity, DataLoader, federation
    websocket-realtime.md # WebSocket/SSE lifecycle, reconnection, ordering, scaling
    feature-flags.md     # Flag types, evaluation, rollout, cleanup, testing, observability
    message-queues.md    # Queue topology, consumer patterns, DLQ, exactly-once, monitoring
    browser-testing.md   # Playwright, page objects, visual regression, Core Web Vitals
    terraform-testing.md # Terraform .tftest.hcl, plan vs apply mode, mock providers
    grpc-services.md     # gRPC proto design, status codes, deadlines, interceptors, health
    i18n-l10n.md         # Text externalization, pluralization, RTL, locale detection
    data-pipelines.md    # Batch/streaming pipelines, idempotency, backfill, data quality
    mlops.md             # Model lifecycle, experiment tracking, drift detection, serving
    ab-testing.md        # Experiment design, power analysis, randomization, analysis
    mobile-development.md # Framework selection, offline support, push notifications
    dashboard-design.md  # Metric grouping, SLO visualization, chart selection, RED method
    documentation-generation.md # OpenAPI, AsyncAPI, TypeDoc, docs-as-code, CI validation
    redis.md             # Atomic operations, key design, TTL, connection management, fallback patterns
    event-driven-architecture.md # CQRS, event sourcing, outbox, saga
    authentication.md    # OAuth 2.1, passkeys, NIST 800-63B, MFA
    monorepo.md          # pnpm workspaces, Turborepo, changesets
    contract-testing.md  # Consumer-driven contracts with Pact
    sre-practices.md     # SLIs, SLOs, error budgets, burn rate alerts
    performance-budgets.md # Core Web Vitals, resource budgets, CI alerts
    zero-downtime-deployments.md # Blue-green, canary, expand-contract
    secrets-management.md # Dynamic secrets, rotation, External Secrets Operator
    container-security.md # Non-root, distroless, image scanning, SLSA
    opentelemetry.md     # SDK init, semantic conventions, sampling, Collector
    privacy-engineering.md # Pseudonymization, retention, erasure, consent
    serverless-edge.md   # Stateless design, cold starts, edge functions
    api-gateway.md       # Gateway vs BFF, circuit breaking, protocol translation
    strangler-fig.md     # Incremental legacy migration through facade
    typescript-5x.md     # using/await using, NoInfer, verbatimModuleSyntax
  agents/                # Custom subagents for specialized delegation (15 agents)
    _shared-principles.md # Shared principles fragment referenced by all agents
    TEMPLATE.md          # Reference template for creating new agents
    accessibility-auditor.md # Accessibility review with WCAG 2.1 AA criteria
    api-reviewer.md      # API backward compatibility and design review
    blast-radius.md      # Trace all consumers of changed interfaces
    code-simplifier.md   # Detect and fix AI-generated code patterns
    coverage-analyzer.md # Test coverage gap analysis and scenario generation
    dependency-analyzer.md # Compare and evaluate packages with structured criteria
    documentation-checker.md # Documentation accuracy verification
    i18n-validator.md    # Translation file validation
    migration-planner.md # Verify migration safety, idempotency, and ordering
    performance-profiler.md # Performance hotspot analysis
    pr-reviewer.md       # Confidence-scored PR review with fix heuristic
    red-team.md          # Adversarial analysis agent
    scope-drift-detector.md # Scope drift detection against plan.md
    security-scanner.md  # SAST + secret + supply chain scanning via Semgrep
    test-scenario-generator.md # Generate test scenarios with priority classification
  skills/                # 30 skills
    assessment/          # Architecture completeness audit
    audit/               # Security audit and dependency management
    benchmark/           # Performance regression detection
    canary/              # Post-deploy monitoring
    checkpoint/          # Save and resume session state
    cso/                 # Chief Security Officer audit (STRIDE/OWASP)
    deploy/              # Post-merge deployment and monitoring
    design/              # Design consultation and variant exploration
    document-release/    # Post-ship documentation sync
    explain/             # Code explanation with diagrams
    fix-issue/           # Fix GitHub issue by number
    guard/               # Combined safety mode
    health/              # Code quality dashboard with scoring
    incident/            # Incident response and postmortems
    infra/               # Docker, Terraform, database operations
    investigate/         # Systematic debugging with hypothesis testing
    learn/               # Operational learnings manager
    migrate/             # Framework and library migration
    morning/             # Start-of-day dashboard
    office-hours/        # Pre-code brainstorming
    palette/             # OKLCH color palette generation
    plan/                # Planning, ADRs, scaffolding
    pr-summary/          # PR summary with reviewer suggestions
    readme/              # README generation
    retro/               # Session retrospective and codebase discovery
    review/              # Code review, QA analysis, design audit
    second-opinion/      # Cross-model code review
    session-log/         # Session activity logger
    ship/                # Delivery: commit, pr, release, checks, worktree
    test/                # Test execution, load testing, coverage, linting
  hooks/
    change-tracker.sh    # File modification logging
    compact-context-saver.sh # Context preservation across compaction
    conventional-commits.sh  # Commit message validation
    dangerous-command-blocker.py  # Catastrophic command prevention
    deslop-checker.sh    # AI-generated code pattern detection (warns only)
    env-file-guard.sh    # Environment and secret file protection
    gh-token-guard.py    # GitHub multi-account token enforcement
    glab-token-guard.py  # GitLab multi-account token enforcement
    failure-logger.py    # Failed tool call logging
    large-file-blocker.sh # Large binary commit prevention
    notify-webhook.sh    # Response completion webhook notification
    scope-guard.sh       # Spec scope enforcement (per-project)
    secret-scanner.py    # Pre-commit secret scanning
    smart-formatter.sh   # Auto-formatting by extension
    tdd-gate.sh          # Test-first enforcement (per-project)
  scripts/
    context-monitor.py   # Statusline: context usage, git, duration, cost
    validate-agents.py   # Agent frontmatter validation (name, description, tools, model)
    validate-counts.py   # Cross-file count reference sync
    validate-patterns.py # Duplicate regex detection in command blocker
    validate-settings.py # Settings.json deny rules and hook path validation
    validate-skills.py   # Skill definition validation
    validate-cross-refs.py # Cross-reference integrity between index, agents, standards
  tests/
    test-hooks.sh        # Hook smoke tests (78 cases)
    fixtures/            # JSON fixtures for hook testing (62 fixtures)
  .github/
    workflows/
      ci.yml             # Lint, validation, hook tests (ubuntu-24.04)
```

</details>

## Configuration

### MCP Servers

42 MCP servers configured in `settings.json`, organized into three groups:

**Stdio servers (no config needed):** Context7, Playwright, Memory, Sequential Thinking, Docker, Lighthouse, Ollama, Filesystem

**Stdio servers (with env vars):** GitHub, GitLab, PostgreSQL, Redis, Slack, Obsidian, Kubernetes, AWS, Cloudflare, Puppeteer, Brave Search, Google Maps, Exa, Firecrawl, Resend, Todoist, Discord, Perplexity, LangSmith

**Remote HTTP servers (zero startup cost):** Sentry, Linear, Figma, Notion, Vercel, Supabase, Atlassian, Mermaid Chart, Excalidraw, Granola, Miro, Asana, Microsoft Learn

### Permissions

76 deny rules protect sensitive files from read, write, and edit access:

- `.env` variants (8 patterns: `.env`, `.env.local`, `.env.production`, `.env.development`, `.env.staging`, `.env.testing`, `.env.ci`, `.env.docker`)
- Home directory credentials (`~/.ssh`, `~/.aws`, `~/.gnupg`, `~/.kube/config`, `~/.docker/config.json`, `~/.npmrc`, `~/.pypirc`, `~/.netrc`)
- Project secrets (`secrets/**`, `config/credentials.json`, `*-credentials.json`, `*.pem`, `*.key`, `*id_rsa*`, `*id_ed25519*`, `*.tfstate`, `*.tfvars`)
- `node_modules` (read denied to prevent context pollution)

The `env-file-guard.sh` hook provides an additional runtime layer that blocks modifications to all protected paths, even if the deny rules are bypassed.

Granular Bash permissions allow common read-only operations without prompting: `git diff`, `git log`, `git status`, `git branch`, `git remote`, `pnpm run`, `npm run`, `npx`.

### Statusline

A custom Python script displays context window usage, git branch, session duration, and cost in the status bar. Context estimation uses transcript file size as a proxy for token usage, with thresholds from green to critical.

### Per-Project Hooks

Two hooks are designed for per-project activation rather than global use:

- **`scope-guard.sh`**: add to a project's `.claude/settings.json` to enforce spec file scope
- **`tdd-gate.sh`**: add to a project's `.claude/settings.json` to require test files before production code

<details>
<summary><strong>How do I add a per-project hook?</strong></summary>
<br>

Add to your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/tdd-gate.sh"
          }
        ]
      }
    ]
  }
}
```

</details>

<details>
<summary><strong>How do I customize or disable a rule?</strong></summary>
<br>

Rules in `rules/` are loaded into context automatically. To disable one, delete or rename the file. To customize, edit the markdown directly. Changes take effect on the next conversation.

</details>

<details>
<summary><strong>How do I add a new skill?</strong></summary>
<br>

Create a directory under `skills/` with a `SKILL.md` file. The file should describe when to trigger, what steps to follow, and what output to produce. See any existing skill for the format.

</details>

<details>
<summary><strong>Why integration tests over unit tests?</strong></summary>
<br>

The testing rule prioritizes integration tests with real databases and services. Unit tests are a fallback for pure functions. The reasoning: a test that mocks the database may pass while the actual query is broken. The mock proves the mock works, not the code. See `rules/testing.md` for the full philosophy.

</details>

## License

[MIT](LICENSE)

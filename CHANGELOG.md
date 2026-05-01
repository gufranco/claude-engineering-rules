# Changelog

All notable changes to this Claude Code configuration are documented here.

## 2026-05-01

### Added

- Hook block feedback loop: every blocking hook now emits a structured JSONL event to `logs/hooks.log` via `scripts/audit_log.py` (with secret redaction, file locking, and 5 MiB rotation). New `retro-pointer.py` Stop hook surfaces a one-line summary at session end when blocks accumulated. `/retro --hooks` mines the log to cluster repeat offenders and propose upstream fixes in rules, skills, or CLAUDE.md so the model self-corrects before the hook fires next time. Hook authoring standard updated with mandatory audit emission patterns for both Python and shell hooks
- Git author identity isolation: a per-remote identity resolution pattern in the user gitconfig via `includeIf "hasconfig:remote.*.url:..."` plus a `git-author-guard` PreToolUse hook that blocks commits with no resolved identity, env-injected author overrides, local `user.*` writes, and pushes carrying placeholder authors. Bypass via `GIT_AUTHOR_GUARD_DISABLE=1`
- New standard documenting the three-layer pattern (declarative gitconfig, defensive hook, documentary standard) with placeholder identities
- 10 new test fixtures and a dedicated section in the hook smoke test runner covering commit, push, and config mutation paths

## 2026-04-29

### Added

- Multi-account CLI safety: parallel terminals targeting different accounts no longer break when one terminal would have switched global state. 6 new PreToolUse hooks hard-block the global-mutation commands and force the per-command form: `docker-context-guard`, `kubectl-context-guard`, `aws-profile-guard`, `gcloud-config-guard`, `terraform-workspace-guard`, `mise-global-guard`
- `standards/multi-account-cli.md`: canonical doc for the per-command pattern across 8 CLIs (gh, glab, docker, kubectl, aws, gcloud, terraform workspace, mise) with detection order, anti-pattern table, and a recipe for adding new tools
- 30 new test fixtures covering blocked and allowed scenarios for every new hook

### Changed

- `gh-token-guard` and `glab-token-guard` error messages now point at `standards/multi-account-cli.md`
- `standards/borrow-restore.md`: rewritten for `mise`, the user's runtime version manager. mise resolves per-project from `.mise.toml`/`.tool-versions` and never mutates a shared "active version", so the borrow-restore fallback is no longer needed for any tool in the toolchain
- `skills/setup`: detects mise via `.mise.toml`/`.tool-versions`/legacy compat files, runs `mise install` + `mise current` once before per-runtime checks
- `skills/assessment`: version manager and CI sections feature mise as Recommended; legacy nvm/asdf/pyenv accepted for compat

## 2026-04-04

### Added

- 10 new rules: context-management, ai-guardrails, changelog, hook-authoring, skill-authoring, mcp-security, performance, privacy, session-hygiene, cost-awareness
- 15 new standards: event-driven-architecture, authentication, monorepo, contract-testing, sre-practices, performance-budgets, zero-downtime-deployments, secrets-management, container-security, opentelemetry, privacy-engineering, serverless-edge, api-gateway, strangler-fig, typescript-5x
- 7 new agents: red-team, api-reviewer, performance-profiler, accessibility-auditor, pr-reviewer, documentation-checker, scope-drift-detector, i18n-validator
- Shared agent principles fragment for consistent constraints across all agents
- 3 new hooks: notify-webhook (Stop), compact-context-saver (PreCompact/PostCompact), failure-logger (PostToolUseFailure)
- 5 new checklist categories: 53 LLM Trust Boundary, 54 Performance Budget, 55 Zero-Downtime Deployment, 56 Supply Chain Security, 57 Event-Driven Architecture
- 2 new CI validation scripts: validate-skills.py, validate-cross-refs.py
- .worktreeinclude for automatic env file propagation to worktrees
- Granular Bash permissions for git, pnpm, npm, and npx commands

### Changed

- settings.json: added includeGitInstructions, autoUpdatesChannel, showThinkingSummaries, worktree symlink config, if-field filtering on conventional-commits hook
- security.md: added OAuth 2.1, passkeys/FIDO2, NIST 800-63B password policy, auth rate limits, secrets management, SBOM/SLSA supply chain requirements
- code-style.md: added LLM Output Trust Boundary, TypeScript 5.x patterns, bisect-friendly commits
- testing.md: added contract testing and performance regression testing sections
- debugging.md: added 3-strike error protocol with failed attempt tracking
- git-workflow.md: added CHANGELOG writing guidance
- verification.md: added post-deploy verification and confidence scoring
- frontend.md: added Core Web Vitals performance budget and AI slop detection
- observability.md: added OpenTelemetry integration section
- api-design.md: added API versioning, rate limiting, and BFF pattern guidance
- database.md: added expand-contract migrations and connection pooling
- infrastructure.md: added zero-downtime deployment strategies
- checklist.md: expanded from 52 to 57 categories
- CLAUDE.md: updated category count references
- index.yml: added 15 new on-demand standard entries

## 2026-04-03

### Added

- Security hardening: 173 patterns in dangerous-command-blocker covering cloud CLI, containers, K8s, databases, IaC, SQL, and reverse shells
- CI pipeline: 3 validation scripts, 20+ test fixtures, 78 total tests
- Deslop checker hook for AI code pattern detection
- Lore commit trailers for decision documentation
- 4 custom agents: code-simplifier, dependency-analyzer, migration-planner, test-scenario-generator

## 2026-04-01

### Added

- 13 rule improvements from field-service-platform session corrections
- i18n regional variant standard with dictionary-based verification
- Semgrep and Qdrant MCP servers
- LLM integration agents

## 2026-03-31

### Added

- Dynamic standard discovery in /assessment and /review skills
- 4 new skills: /investigate, /deploy, /design, /second-opinion
- Browser testing standard
- Checklist categories 51 (Deployment Verification) and 52 (Design Quality)

## 2026-03-27

### Added

- Gap analysis: 102 findings across hooks, settings, CI, skills, rules, standards, and checklist
- Multi-tenancy, accessibility-testing, and cost-optimization standards
- GraphQL, WebSocket, message-queues, and feature-flags standards

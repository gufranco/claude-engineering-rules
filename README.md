<div align="center">

<strong>An opinionated engineering config for Claude Code. Rules, runtime hooks, and slash-command skills that turn the CLI into a strict pair-programmer.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/claude-engineering-rules/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/claude-engineering-rules/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

</div>

**11** always-on rules · **63** on-demand standards · **30** slash-command skills · **33** runtime hooks · **9** custom agents · **36** MCP servers · **774** review items across **69** categories

---

<table>
<tr>
<td width="50%" valign="top">

### Runtime Guardrails
33 hooks intercept tool calls before they run. They block destructive commands, secrets in commits, mutating method calls, AI co-author trailers, and 30+ other failure patterns.

</td>
<td width="50%" valign="top">

### Two-Tier Rule Loading
11 universal rules ship with every conversation. 63 domain standards load only when `rules/index.yml` triggers match the task. Most sessions pull 2-5 standards instead of all 63.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 30 Slash-Command Skills
`/ship`, `/review`, `/plan`, `/audit`, `/investigate`, `/research`, and 24 more. Each is a documented multi-step workflow with subcommands, not a one-liner.

</td>
<td width="50%" valign="top">

### Anti-Hallucination by Design
Verify-before-claim is a rule, not a suggestion. Read the file, run the command, check the output. "It should work" is not evidence.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 774-Item Review Checklist
One file, 69 categories: correctness, security, error handling, concurrency, data integrity, observability, accessibility, performance budgets, supply chain. Apply by category, not by ceremony.

</td>
<td width="50%" valign="top">

### Mutation-Free TypeScript
The mutation-method-blocker hook flags 90+ in-place mutation patterns across arrays, Maps, Sets, Dates, `Object.assign`, `delete`, compound assignment, and parameter reassignment. Auto-allows Immer, Redux Toolkit, Pinia, MobX, Zustand, Svelte runes, and 15 other state libs.

</td>
</tr>
</table>

## The Problem

Claude Code is capable but uncritical. It will mock the database when you said never mock. It will write `as any` to make TypeScript stop complaining. It will declare a task done without running tests. Without guardrails, the model regresses toward whatever pattern is most common in its training set, not whatever your codebase actually needs.

## The Solution

A layered config where each layer catches what the layer above missed.

| Layer | What it enforces | When it runs |
|:------|:-----------------|:-------------|
| `CLAUDE.md` + `rules/` | Always-on engineering rules, tone, anti-hallucination, verification gates | Every conversation |
| `standards/` + `rules/index.yml` | Domain expertise that loads on trigger keywords | When the task needs it |
| `hooks/` | Runtime blocks for destructive commands, secrets, banned patterns | Before every tool call |
| `skills/` | Documented multi-step workflows: ship, review, plan, audit | When the user invokes `/<name>` |
| `agents/` | Specialized subagents for focused review tasks | When delegated explicitly |
| `checklists/` | 774-item review checklist for code, infra, and process | On demand during review |

## What's Included

### Rules, always loaded

11 rules in [`rules/`](rules/), loaded into every conversation.

| Rule | What it covers |
|:-----|:---------------|
| [`code-style`](rules/code-style.md) | DRY/SOLID/KISS, immutability, error classification, branded types, completeness rule |
| [`testing`](rules/testing.md) | Integration-first, strict mock policy, AAA pattern, fake data, deterministic tests |
| [`security`](rules/security.md) | Secrets, auth, encryption, data privacy, audit logging, supply chain |
| [`git-workflow`](rules/git-workflow.md) | Conventional commits, branches, CI monitoring, PRs |
| [`verification`](rules/verification.md) | Evidence-based completion gates, response self-check |
| [`writing-precision`](rules/writing-precision.md) | Precision gate for all text output |
| [`pre-flight`](rules/pre-flight.md) | Duplicate check, market research, architecture fit, interface verification |
| [`surgical-edits`](rules/surgical-edits.md) | Every changed line traces to the request |
| [`ai-guardrails`](rules/ai-guardrails.md) | AI output review, plan before generating, multi-agent validation |
| [`memory-supersede`](rules/memory-supersede.md) | Supersede-not-delete for project and feedback memories |
| [`language`](rules/language.md) | Response language enforcement: all output in English |

Plus 4 language-specific files in [`rules/lang/`](rules/lang/): `typescript-immutability`, `typescript-types`, `typescript-strict`, `prisma-migrations`.

### Standards, loaded on demand

63 standards in [`standards/`](standards/). Each entry in [`rules/index.yml`](rules/index.yml) declares trigger keywords. When a task matches, only those standards load.

Topics: API design, authentication, caching, code review, container security, contract testing, database, DDD, debugging, distributed systems, documentation, frontend, GraphQL, hexagonal architecture, i18n, infrastructure, message queues, mobile, monorepo, observability, OpenTelemetry, performance, postgres, privacy, redis, resilience, secrets management, SRE, state machines, twelve-factor, TypeScript 5.x, WebSocket, zero-downtime deployments, and more.

### Skills

30 skills in [`skills/`](skills/). Each is a folder with a `SKILL.md` that documents steps, output format, and rules.

| Skill | What it does |
|:------|:-------------|
| `/ship` | Delivery pipeline: commit, PR, release, CI checks, worktrees |
| `/review` | Three-pass code review, QA analysis, visual audit |
| `/plan` | Spec folders with discovery, scope review, ADRs, scaffolding |
| `/audit` | Security audit, threat modeling, supply chain checks |
| `/test` | Test execution, perf, lint, CI smoke, stub generation |
| `/deploy` | Post-merge landing and canary monitoring |
| `/investigate` | Systematic debugging with hypothesis testing, 3-strike limit |
| `/research` | Multi-source research with entity resolution and citation discipline |
| `/design` | Design consultation, variants, design-system work |
| `/refactor` | Guided refactoring with behavior preservation |
| `/migrate` | Framework or library migration with incremental testing |
| `/infra` | Container orchestration, IaC, database migrations |
| `/hotfix` | Emergency production fix with expedited workflow |
| `/incident` | Incident context gathering, blameless postmortem |
| `/resolve` | Merge conflict resolution with verification |
| `/cleanup` | Stale branch, PR, and worktree cleanup |
| `/checkpoint` | Save and resume state across sessions |
| `/explain` | Code explanation with Mermaid diagrams |
| `/fix-issue` | Fix a GitHub issue by number with tests |
| `/guard` | Directory freeze and scope enforcement |
| `/benchmark` | Performance regression detection with baselines |
| `/profile` | N+1 queries, missing indexes, complexity hot spots |
| `/onboard` | Codebase onboarding: architecture map, "Start Here" |
| `/pr-summary` | PR summary with reviewer suggestions |
| `/readme` | README generation from codebase analysis |
| `/retro` | Session retrospective with pattern extraction |
| `/session-log` | Session activity logger for handoff |
| `/setup` | Interactive project environment setup |
| `/tdd` | Test-driven development loop |
| `/zoom-out` | Step back from tactical work to strategic view |

### Hooks

33 hooks in [`hooks/`](hooks/) wired through `settings.json`. Each runs before, after, or around a tool call.

| Hook | Trigger | What it does |
|:-----|:--------|:-------------|
| `dangerous-command-blocker.py` | PreToolUse Bash | 150+ patterns: destructive shell commands, reverse shells, cloud deletions, IaC destroy |
| `secret-scanner.py` | PreToolUse Bash | 40+ secret patterns before git commit |
| `conventional-commits.sh` | PreToolUse Bash | Validates conventional commit format |
| `gh-token-guard.py` | PreToolUse Bash | Requires inline `GH_TOKEN`, blocks `gh auth switch` |
| `glab-token-guard.py` | PreToolUse Bash | Requires inline `GITLAB_TOKEN`, blocks GitLab auth login |
| `docker-context-guard.py` | PreToolUse Bash | Forces `--context` or `DOCKER_CONTEXT` per call |
| `kubectl-context-guard.py` | PreToolUse Bash | Forces `--context` or `KUBECONFIG` per call |
| `aws-profile-guard.py` | PreToolUse Bash | Blocks `aws configure set` without `--profile` |
| `gcloud-config-guard.py` | PreToolUse Bash | Forces `--configuration` per call |
| `terraform-workspace-guard.py` | PreToolUse Bash | Forces `TF_WORKSPACE` per call |
| `mise-global-guard.py` | PreToolUse Bash | Blocks `mise use --global`, forces project-local config |
| `git-author-guard.py` | PreToolUse Bash | Blocks commits with unresolved identity or placeholder authors |
| `large-file-blocker.sh` | PreToolUse Bash | Blocks commits with files over 5MB |
| `env-file-guard.sh` | PreToolUse Write/Edit | Blocks edits to `.env`, private keys, cloud creds, tfstate |
| `rtk-rewrite.sh` | PreToolUse Bash | Rewrites CLI commands through RTK for token savings |
| `ai-attribution-blocker.py` | PreToolUse Bash/Write/Edit | Blocks AI co-author trailers in commits and PRs |
| `as-any-blocker.py` | PreToolUse Write/Edit | Blocks TypeScript `as any` and generic `any` |
| `banned-phrases-blocker.py` | PreToolUse Bash/Write/Edit | Blocks conversational fluff phrases in PRs and docs |
| `banned-prose-chars.py` | PreToolUse Write/Edit/Bash | Blocks em dashes, parens in prose, emojis, ASCII art |
| `console-log-blocker.py` | PreToolUse Write/Edit | Blocks `console.*` in non-test code |
| `internal-config-leakage.py` | PreToolUse Bash/Write/Edit | Prevents internal config references in external output |
| `migration-idempotency.py` | PreToolUse Write/Edit | Forces `IF NOT EXISTS` / `IF EXISTS` on DDL |
| `mock-internal-blocker.py` | PreToolUse Write/Edit | Blocks mocking own services, DB, Redis, queues in tests |
| `mutation-method-blocker.py` | PreToolUse Write/Edit/MultiEdit | Blocks 90+ in-place mutation patterns in JS/TS |
| `prisma-raw-sql-blocker.py` | PreToolUse Write/Edit | Blocks Prisma raw query escape hatches |
| `prisma-schema-sync.py` | PreToolUse Write/Edit | Enforces schema.prisma vs migration parity |
| `redis-atomicity.py` | PreToolUse Write/Edit | Forces atomic Redis sequences via Lua/MULTI |
| `settings-hygiene.py` | PreToolUse Write/Edit/MultiEdit | Blocks credentials and absolute home paths in settings |
| `english-only-reminder.sh` | UserPromptSubmit | Injects system-reminder forcing English assistant output |
| `smart-formatter.sh` | PostToolUse Edit/Write | Auto-formats: prettier, black, gofmt, rustfmt, shfmt |
| `notify-webhook.sh` | Stop | POST to `CLAUDE_NOTIFY_WEBHOOK` on response completion |
| `retro-pointer.py` | Stop | One-line summary at session end when blocks accumulated |
| `compact-context-saver.sh` | SessionStart / PreCompact / PostCompact | Preserves git status across compaction |

### Custom Agents

9 specialized subagents in [`agents/`](agents/). Each follows the agent template.

| Agent | Purpose |
|:------|:--------|
| [`accessibility-auditor`](agents/accessibility-auditor.md) | WCAG 2.1 AA accessibility review |
| [`api-reviewer`](agents/api-reviewer.md) | API backward compatibility and design review |
| [`blast-radius`](agents/blast-radius.md) | Trace all consumers of changed interfaces |
| [`documentation-checker`](agents/documentation-checker.md) | Documentation accuracy vs codebase |
| [`i18n-validator`](agents/i18n-validator.md) | Translation file validation |
| [`migration-planner`](agents/migration-planner.md) | Database migration safety and ordering |
| [`red-team`](agents/red-team.md) | Adversarial analysis: attack happy paths |
| [`scope-drift-detector`](agents/scope-drift-detector.md) | Compare diff against plan for scope drift |
| [`test-scenario-generator`](agents/test-scenario-generator.md) | Test scenarios with priority and traceability |

### Workflow Decision Guide

| Scenario | Start with |
|:---------|:-----------|
| "I need to build X" | `/plan --discover` then implement |
| "Something is broken" | `/investigate` |
| "Can you review this PR?" | `/review` |
| "Is my code ready to ship?" | `/review --local` then `/ship` |
| "Are we secure?" | `/audit` |
| "Time to release" | `/ship release` |
| "CI is failing" | `/ship checks` |
| "Prod is broken, fix NOW" | `/hotfix` |
| "Just joined this project" | `/onboard` |
| "What does the community say about X" | `/research X` |
| "X vs Y, which is better" | `/research X vs Y` |
| "This code needs restructuring" | `/refactor` |

## Quick Start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Claude Code | Latest | [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |
| Git | >= 2.0 | Pre-installed on macOS |
| Python 3 | >= 3.8 | Pre-installed on macOS |
| jq | >= 1.6 | `brew install jq` |
| RTK | >= 0.23.0 | `cargo install rtk` |

### Setup

```bash
git clone git@github.com:gufranco/claude-engineering-rules.git
cd claude-engineering-rules

# Symlink into the Claude config directory, stays in sync with git
ln -sf "$(pwd)/"* "$HOME/.claude/"
```

### Verify

Open Claude Code in any project and run:

```bash
/ship commit
```

The hooks, rules, and skills activate automatically.

## Configuration

### MCP Servers

36 MCP servers wired in `settings.json` across three transports:

- **Stdio, no env:** Playwright, Memory, Sequential Thinking, Docker, Lighthouse, Ollama, Filesystem
- **Stdio with env:** GitHub, GitLab, PostgreSQL, Redis, Slack, Obsidian, Kubernetes, AWS, Cloudflare, Puppeteer, Brave Search, Google Maps, Firecrawl, Resend, Todoist, Discord, Perplexity, LangSmith, Semgrep, Qdrant
- **Remote HTTP, zero startup:** Sentry, Linear, Figma, Notion, Vercel, Supabase, Atlassian, Mermaid Chart, Asana

### Permissions

- **76 deny rules** protect sensitive files: `.env` variants, SSH keys, AWS creds, GnuPG, `*.pem`, `*.key`, `*.tfstate`, `node_modules`
- **21 allow rules** enable read-only operations without prompting: `git diff`, `git log`, `git status`, `pnpm run`, `npx`

The `env-file-guard.sh` hook adds a runtime layer that catches anything permissions miss.

<details>
<summary><strong>Project structure</strong></summary>

```
$HOME/.claude/
  CLAUDE.md          Core engineering rules, always loaded
  RTK.md             RTK token-optimized CLI proxy reference
  settings.json      Permissions, hooks, MCP servers
  checklists/        Unified 774-item review checklist
  rules/             11 always-on rules plus 4 language-specific
    index.yml        Rule and standard catalog with trigger keywords
    lang/            TypeScript and Prisma rules
  standards/         63 on-demand domain standards
  agents/            9 specialized subagents
  skills/            30 slash-command skills
  hooks/             33 runtime hooks
  scripts/           Validation and maintenance scripts
  tests/             Hook smoke tests
  .github/workflows/ Lint, validation, hook tests
```

</details>

## FAQ

<details>
<summary><strong>How do I customize or disable a rule?</strong></summary>
<br>

Rules in `rules/` load into context automatically. To disable one, delete or rename the file. To customize, edit the markdown. Changes take effect on the next conversation.

</details>

<details>
<summary><strong>How do I add a new skill?</strong></summary>
<br>

Create a directory under `skills/` with a `SKILL.md` file. Use frontmatter: `name`, `description` for trigger matching, then the skill body with steps and rules. See any existing skill for the shape.

</details>

<details>
<summary><strong>Why integration tests over unit tests?</strong></summary>
<br>

The testing rule treats unit tests as a fallback for pure functions. A test that mocks the database may pass while the actual query is broken. The mock proves the mock works, not the code. See [`rules/testing.md`](rules/testing.md).

</details>

<details>
<summary><strong>How does two-tier rule loading save context?</strong></summary>
<br>

The 63 standards total roughly 12,000 lines. Loading all of them into every conversation would burn the context window. `rules/index.yml` maps each standard to trigger keywords. When a task matches, e.g. "add a database migration" pulls `database.md`, only the relevant standards load. Most conversations need 2-5 standards.

</details>

<details>
<summary><strong>What does the dangerous command blocker cover?</strong></summary>
<br>

150+ patterns: filesystem destruction, privilege escalation, reverse shells, git destructive operations, AWS/GCP/Azure CLI deletions, Vercel/Netlify/Firebase, Docker and Kubernetes destructive commands, database CLI drops, IaC destroy, SQL statements without WHERE, credential exfiltration.

</details>

## License

[MIT](LICENSE)

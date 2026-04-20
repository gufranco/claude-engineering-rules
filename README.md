<div align="center">

<strong>Ship code that passes review the first time. 9 rules, 68 on-demand standards, 40 skills, 36 MCP servers, 11 runtime hooks, and 9 custom agents that turn Claude Code into an opinionated engineering partner.</strong>

<br>
<br>

[![CI](https://img.shields.io/github/actions/workflow/status/gufranco/claude-engineering-rules/ci.yml?style=flat-square&label=CI)](https://github.com/gufranco/claude-engineering-rules/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/gufranco/claude-engineering-rules?style=flat-square)](LICENSE)

</div>

---

**9** rules · **68** standards · **40** skills · **36** MCP servers · **11** hooks · **9** agents · **649** checklist items · **58** categories · **25,000+** lines of engineering configuration

<table>
<tr>
<td width="50%" valign="top">

### Runtime Guardrails

Eleven hooks intercept tool calls in real time: block destructive commands across 150+ patterns, scan for secrets from 40+ providers, enforce conventional commits, prevent large file commits, guard environment files, enforce multi-account token safety for GitHub and GitLab, rewrite CLI commands through RTK for 60-90% token savings, and auto-format code on every edit.

</td>
<td width="50%" valign="top">

### Two-Tier Rule Loading

9 universal rules load automatically. 68 domain-specific standards load on demand, matched by trigger keywords from `rules/index.yml`. Saves ~51KB of context per conversation by loading specialist standards only when triggered.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 40 Slash-Command Skills

`/ship`, `/review`, `/test`, `/audit`, `/plan`, `/investigate`, and 34 more. Each skill orchestrates multi-step workflows with a single command: delivery pipelines, three-pass code review, STRIDE threat modeling, systematic debugging with 3-strike escalation, and architecture planning with spec folders.

</td>
<td width="50%" valign="top">

### Anti-Hallucination by Design

Mandatory verification gates: every file path, import, and API call verified before use. Pre-flight checks before implementation. Response self-check for analytical output. Prompt injection guards on skills that process external content. "Never guess" policy across all rules.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 649-Item Review Checklist

Single unified checklist spanning 58 categories: correctness, security, error handling, concurrency, data integrity, testing, architecture patterns, deployment verification, LLM trust boundary, performance budgets, zero-downtime deployment, supply chain security, event-driven architecture, and licensing compliance.

</td>
<td width="50%" valign="top">

### Clean Room Verification

30+ checks across seven sections prevent plagiarism when using external projects as reference. Structural, naming, logic, license, and documentation independence gates with similarity thresholds. Mandatory closing gate on every plan.

</td>
</tr>
</table>

## The Problem

Claude Code is capable out of the box, but it does not enforce your engineering standards. It will mock your database in tests, commit with vague messages, skip CI checks, guess import paths, and write code that passes locally but fails in review. Every conversation starts from zero, with no memory of how your team works.

## The Solution

This configuration turns Claude Code into an opinionated engineering partner. Rules define what it should do. Hooks enforce it at runtime. Skills automate multi-step workflows. Standards load on demand so context stays small.

| Capability | Vanilla Claude Code | With This Config |
|:-----------|:-------------------:|:----------------:|
| Commit message enforcement | No | Conventional commits validated by hook |
| Secret scanning before commit | No | 40+ provider-specific patterns |
| Destructive command blocking | No | 150+ patterns across cloud, k8s, DB, IaC |
| Multi-account token safety | No | Inline token required for `gh` and `glab` |
| Integration-first test policy | No | Real DB, strict mock ban, AAA pattern |
| Pre-flight verification | No | Duplicate check, architecture fit, interface verification |
| On-demand domain standards | No | 68 standards, ~51KB saved per conversation |
| Workflow automation | No | 40 skills with subcommands |
| MCP server integrations | No | 36 servers: GitHub, Slack, Sentry, Linear, Figma, and more |
| Code review checklist | No | 649 items across 58 categories |
| Clean room plagiarism prevention | No | 30+ checks across 7 independence sections |

## How It Works

```mermaid
graph LR
    subgraph Input
        A[User Command]
    end
    subgraph PreToolUse Hooks
        B[Dangerous Command Blocker]
        C[Secret Scanner]
        D[Conventional Commits]
        B2[GH/GLab Token Guards]
        E2[Large File Blocker]
        F2[Env File Guard]
        R[RTK Rewrite]
    end
    subgraph Claude Code
        E[CLAUDE.md Rules]
        F[On-Demand Standards]
        G[Skills]
    end
    subgraph PostToolUse Hooks
        H[Smart Formatter]
    end
    A --> B & C & D & B2 & E2 & F2 & R
    B & C & D & B2 & E2 & F2 & R --> E
    E --> F
    F --> G
    G --> H
```

**Rules** define what Claude should do. **Hooks** enforce it at runtime. **Skills** automate multi-step workflows.

## What's Included

### Rules (always loaded)

9 rules in [`rules/`](rules/), loaded into every conversation automatically.

| Rule | What it covers |
|:-----|:---------------|
| [`code-style`](rules/code-style.md) | DRY/SOLID/KISS, immutability, error classification, branded types, TypeScript conventions |
| [`testing`](rules/testing.md) | Integration-first, strict mock policy, AAA pattern, fake data, deterministic tests |
| [`security`](rules/security.md) | Secrets, auth, encryption, data privacy, audit logging, supply chain security |
| [`git-workflow`](rules/git-workflow.md) | Conventional commits, branches, CI monitoring, PRs, conflict resolution |
| [`verification`](rules/verification.md) | Evidence-based completion gates, response self-check, no claim without fresh evidence |
| [`writing-precision`](rules/writing-precision.md) | Precision gate for all text: concrete over abstract, examples over vague instructions |
| [`pre-flight`](rules/pre-flight.md) | Duplicate check, market research, architecture fit, interface verification |
| [`ai-guardrails`](rules/ai-guardrails.md) | AI output review, plan before generating, multi-agent validation |
| [`language`](rules/language.md) | Response language enforcement: all output in English |

### Standards (loaded on demand)

68 standards in [`standards/`](standards/), loaded only when the task matches trigger keywords from [`rules/index.yml`](rules/index.yml).

Covers: API design, authentication, caching, database, distributed systems, frontend, GraphQL, gRPC, hexagonal architecture, i18n, infrastructure, message queues, microservices, monorepo, observability, privacy, resilience, serverless, state machines, Terraform testing, TypeScript 5.x, WebSocket, and 40+ more.

### Skills

40 skills in [`skills/`](skills/). Each has a `SKILL.md` with full documentation.

| Skill | Subcommands | What it does |
|:------|:------------|:-------------|
| `/ship` | `commit`, `pr`, `release`, `checks`, `worktree` | Delivery pipeline: semantic commits, PRs with CI monitoring, releases |
| `/deploy` | `land`, `canary` | Post-merge deployment, canary monitoring |
| `/review` | `code`, `qa`, `design` | Three-pass code review, QA analysis, visual/accessibility audit |
| `/audit` | `deps`, `secrets`, `docker`, `code`, `scan`, `image`, `threat`, `daily`, `comprehensive` | Security audit, STRIDE/OWASP threat modeling, supply chain |
| `/test` | `perf`, `lint`, `scan`, `ci`, `stubs` | Test execution, load testing, coverage, security scanning |
| `/plan` | `adr`, `scaffold` | Structured planning with spec folders, ADRs, scaffolding |
| `/investigate` | `--freeze` | Systematic debugging with hypothesis testing, 3-strike limit |
| `/design` | `consult`, `variants`, `system` | Design consultation, variant exploration, design system |
| `/second-opinion` | `--mode gate/adversarial/consult` | Cross-model review via Ollama, OpenAI, or other providers |
| `/infra` | `docker`, `terraform`, `db` | Container orchestration, IaC workflows, database migrations |
| `/retro` | `discover`, `--curate`, `--promote` | Session retrospective, pattern extraction, rule graduation |
| `/assessment` | -- | Architecture completeness audit against 58-category checklist |
| `/morning` | -- | Start-of-day dashboard: open PRs, pending reviews, standup prep |
| `/incident` | -- | Incident context gathering, blameless postmortem |
| `/guard` | `<directory>`, `off` | Directory freeze + destructive command warnings + scope enforcement |
| `/benchmark` | `api`, `bundle`, `--save` | Performance regression detection with baselines |
| `/health` | -- | Code quality dashboard with weighted 0-10 score |
| `/profile` | `--db`, `--api` | N+1 queries, missing indexes, O(n^2) detection |
| `/refactor` | `--plan-only` | Guided refactoring with behavior preservation |
| `/hotfix` | -- | Emergency production fix with expedited workflow |
| `/onboard` | -- | Codebase onboarding: architecture map, "Start Here" guide |
| `/fix-issue` | `<number>` | Fix a GitHub issue by number with tests and commit |
| `/breaking-change` | `--plan-only` | API breaking change management with deprecation plan |
| `/migrate` | `<from> <to>` | Framework/library migration with incremental testing |
| `/tech-debt` | `--critical` | TODO/FIXME/HACK scanning with prioritization |
| `/cleanup` | `branches`, `prs`, `worktrees` | Stale branch/PR/worktree cleanup |
| `/setup` | -- | Interactive project environment setup |
| `/resolve` | -- | Merge conflict resolution with verification |
| `/weekly` | `<N>`, `--sprint` | Sprint/week summary with delivery metrics |
| `/checkpoint` | `save`, `resume`, `list` | Save and resume state across sessions |
| `/readme` | -- | README generation from codebase analysis |
| `/palette` | -- | Accessible OKLCH color palette for Tailwind CSS |
| `/explain` | `--depth shallow/deep` | Code explanation with Mermaid diagrams |
| `/pr-summary` | `<number>` | PR summary with reviewer suggestions |
| `/document-release` | -- | Post-ship documentation sync |
| `/canary` | `<duration>`, `<url>` | Post-deploy HTTP monitoring |
| `/learn` | `show`, `search`, `add` | Operational learnings manager across sessions |
| `/session-log` | `export` | Session activity logger for handoff |
| `/office-hours` | -- | Pre-code brainstorming with forcing questions |
| `/graphify` | -- | Input to knowledge graph with clustering |

### Hooks

11 hooks in [`hooks/`](hooks/), intercepting tool calls at runtime.

| Hook | Trigger | What it does |
|:-----|:--------|:-------------|
| [`dangerous-command-blocker.py`](hooks/dangerous-command-blocker.py) | PreToolUse (Bash) | 150+ patterns: rm -rf, reverse shells, cloud CLI deletions, database drops, IaC destroy |
| [`secret-scanner.py`](hooks/secret-scanner.py) | PreToolUse (Bash) | 40+ secret patterns before git commit: AWS, Stripe, GCP, Azure, GitHub, and more |
| [`conventional-commits.sh`](hooks/conventional-commits.sh) | PreToolUse (Bash) | Validates commit messages match conventional commit format |
| [`gh-token-guard.py`](hooks/gh-token-guard.py) | PreToolUse (Bash) | Requires inline `GH_TOKEN`, blocks `gh auth switch` |
| [`glab-token-guard.py`](hooks/glab-token-guard.py) | PreToolUse (Bash) | Requires inline `GITLAB_TOKEN`, blocks `glab auth login` |
| [`large-file-blocker.sh`](hooks/large-file-blocker.sh) | PreToolUse (Bash) | Blocks commits with files over 5MB |
| [`env-file-guard.sh`](hooks/env-file-guard.sh) | PreToolUse (Write/Edit) | Blocks `.env`, private keys, cloud credentials, Terraform state |
| [`rtk-rewrite.sh`](hooks/rtk-rewrite.sh) | PreToolUse (Bash) | Rewrites CLI commands through RTK for 60-90% token savings |
| [`smart-formatter.sh`](hooks/smart-formatter.sh) | PostToolUse (Edit/Write) | Auto-formats by extension: prettier, black, gofmt, rustfmt, shfmt |
| [`notify-webhook.sh`](hooks/notify-webhook.sh) | Stop | POST to `CLAUDE_NOTIFY_WEBHOOK` on response completion |
| [`compact-context-saver.sh`](hooks/compact-context-saver.sh) | SessionStart/PreCompact/PostCompact | Preserves git status and branch across context compaction |

### Custom Agents

9 specialized subagents in [`agents/`](agents/). Each follows [`TEMPLATE.md`](agents/TEMPLATE.md).

| Agent | Model | Purpose |
|:------|:------|:--------|
| [`accessibility-auditor`](agents/accessibility-auditor.md) | Sonnet | WCAG 2.1 AA accessibility review |
| [`api-reviewer`](agents/api-reviewer.md) | Sonnet | API backward compatibility and design review |
| [`blast-radius`](agents/blast-radius.md) | Haiku | Trace all consumers of changed interfaces |
| [`documentation-checker`](agents/documentation-checker.md) | Haiku | Documentation accuracy vs codebase verification |
| [`i18n-validator`](agents/i18n-validator.md) | Haiku | Translation file validation: missing keys, diacritical marks |
| [`migration-planner`](agents/migration-planner.md) | Haiku | Database migration safety, idempotency, ordering |
| [`red-team`](agents/red-team.md) | Sonnet | Adversarial analysis: attack happy paths, exploit trust assumptions |
| [`scope-drift-detector`](agents/scope-drift-detector.md) | Haiku | Compare diff against plan.md for unplanned scope |
| [`test-scenario-generator`](agents/test-scenario-generator.md) | Sonnet | Test scenarios with priority classification and traceability |

### Workflow Decision Guide

| Scenario | Start with |
|:---------|:-----------|
| "I need to build X" | `/plan --discover` then implement |
| "Something is broken" | `/investigate` |
| "Can you review this PR?" | `/review 142` |
| "Is my code ready to ship?" | `/review --local` |
| "Is this project production-ready?" | `/assessment` |
| "Are we secure?" | `/audit` or `/audit comprehensive` |
| "Any vulnerable dependencies?" | `/audit deps` |
| "Time to release" | `/ship release` |
| "CI is failing" | `/ship checks` |
| "Run tests" | `/test` |
| "What did we ship this week?" | `/weekly` |
| "Prod is broken, fix NOW" | `/hotfix` |
| "Just joined this project" | `/onboard` |
| "This code needs restructuring" | `/refactor` |
| "Need a second opinion" | `/second-opinion --mode adversarial` |

## Quick Start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Claude Code | Latest | [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |
| Git | >= 2.0 | Pre-installed on macOS |
| Python 3 | >= 3.8 | Pre-installed on macOS |
| jq | >= 1.6 | `brew install jq` |
| RTK | >= 0.23.0 | `cargo install rtk` or see [rtk-ai/rtk](https://github.com/rtk-ai/rtk) |

### Setup

```bash
git clone git@github.com:gufranco/claude-engineering-rules.git
cd claude-engineering-rules
```

Symlink or copy the contents into `~/.claude/`:

```bash
# Option A: symlink (recommended, stays in sync with git)
ln -sf "$(pwd)/"* ~/.claude/

# Option B: copy
cp -r ./* ~/.claude/
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
  CLAUDE.md              # Core engineering rules
  RTK.md                 # RTK token-optimized CLI proxy documentation
  settings.json          # Permissions, hooks, MCP servers, statusline
  checklists/
    checklist.md         # 649-item unified checklist across 58 categories
  rules/                 # Always loaded (9 rules)
    index.yml            # Rule + standard catalog with trigger keywords
  standards/             # Loaded on demand (68 standards)
  agents/                # Custom subagents (9 agents)
    TEMPLATE.md          # Agent template
  skills/                # 40 skills with SKILL.md each
  hooks/                 # 11 runtime hooks
  scripts/               # Validation, benchmarking, statusline
  tests/
    test-hooks.sh        # Hook smoke tests (63 fixtures)
  .github/
    workflows/
      ci.yml             # Lint, validation, hook tests (ubuntu-24.04)
```

</details>

## Configuration

### MCP Servers

36 MCP servers in `settings.json`:

**Stdio (no config):** Playwright, Memory, Sequential Thinking, Docker, Lighthouse, Ollama, Filesystem

**Stdio (with env vars):** GitHub, GitLab, PostgreSQL, Redis, Slack, Obsidian, Kubernetes, AWS, Cloudflare, Puppeteer, Brave Search, Google Maps, Firecrawl, Resend, Todoist, Discord, Perplexity, LangSmith, Semgrep, Qdrant

**Remote HTTP (zero startup cost):** Sentry, Linear, Figma, Notion, Vercel, Supabase, Atlassian, Mermaid Chart, Asana

### Permissions

76 deny rules protect sensitive files: `.env` variants, `~/.ssh`, `~/.aws`, `~/.gnupg`, `*.pem`, `*.key`, `*.tfstate`, `node_modules`, and more. The `env-file-guard.sh` hook provides an additional runtime enforcement layer.

21 allow rules enable common read-only operations without prompting: `git diff`, `git log`, `git status`, `git branch`, `pnpm run`, `npm run`, `npx`.

## FAQ

<details>
<summary><strong>How do I customize or disable a rule?</strong></summary>
<br>

Rules in `rules/` are loaded into context automatically. To disable one, delete or rename the file. To customize, edit the markdown directly. Changes take effect on the next conversation.

</details>

<details>
<summary><strong>How do I add a new skill?</strong></summary>
<br>

Create a directory under `skills/` with a `SKILL.md` file. Use the frontmatter format: `name`, `description` (triggers), and the skill body with steps, output format, and rules. See any existing skill for the structure.

</details>

<details>
<summary><strong>How do I add a new agent?</strong></summary>
<br>

Copy `agents/TEMPLATE.md` and fill in each section: identity, constraints, process, output contract, scenario handling, and final checklist. Key rules: agents must not spawn subagents, must specify exact output format, and must include a verification checklist.

</details>

<details>
<summary><strong>Why integration tests over unit tests?</strong></summary>
<br>

The testing rule prioritizes integration tests with real databases and services. Unit tests are a fallback for pure functions. A test that mocks the database may pass while the actual query is broken. The mock proves the mock works, not the code. See [`rules/testing.md`](rules/testing.md).

</details>

<details>
<summary><strong>How does two-tier rule loading save context?</strong></summary>
<br>

The 68 standards total ~14,000 lines. Loading all of them into every conversation would consume ~51KB of context window. Instead, `rules/index.yml` maps each standard to trigger keywords. When a task matches (e.g., "add a database migration" triggers `database.md`), only the relevant standards load. Most conversations need 2-5 standards, saving 90%+ of the context budget.

</details>

<details>
<summary><strong>What does the dangerous command blocker cover?</strong></summary>
<br>

150+ patterns across: filesystem destruction (rm -rf, dd, mkfs), privilege escalation (sudo + destructive), reverse shells, git destructive operations (force push, filter-branch), AWS/GCP/Azure CLI deletions, platform CLI (Vercel, Netlify, Firebase), Docker/Kubernetes destructive commands, database CLI drops (Redis, MongoDB, PostgreSQL, MySQL), IaC destroy (Terraform, Pulumi, CDK), SQL statements without WHERE clauses, and credential exfiltration attempts.

</details>

## License

[MIT](LICENSE)

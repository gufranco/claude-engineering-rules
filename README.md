<div align="center">

<strong>An opinionated engineering config for Claude Code. Rules, runtime hooks, and slash-command skills that turn the CLI into a strict pair-programmer.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/claude-engineering-rules/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/claude-engineering-rules/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

</div>

**17** always-on rules · **69** on-demand standards · **36** slash-command skills · **52** runtime hooks · **15** custom agents · **36** MCP servers · **869** review items across **71** categories

---

<table>
<tr>
<td width="50%" valign="top">

### Runtime Guardrails
52 hooks intercept tool calls before they run. They block destructive commands, secrets in commits, mutating method calls, AI co-author trailers, banned phrases, internal config leakage, and 40+ other failure patterns.

</td>
<td width="50%" valign="top">

### Two-Tier Rule Loading
19 universal rules ship with every conversation. 65 domain standards load only when [`rules/index.yml`](rules/index.yml) triggers match the task. Most sessions pull 2-5 standards instead of all 65.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 33 Slash-Command Skills
`/ship`, `/review`, `/respond`, `/assessment`, `/plan`, `/audit`, `/onboard`, `/investigate`, `/research`, and 24 more. Each is a documented multi-step workflow with subcommands, not a one-liner. `/audit trust` and `/onboard --verify` catch malicious code in untrusted projects before any install runs.

</td>
<td width="50%" valign="top">

### Anti-Hallucination by Design
Verify-before-claim is a rule, not a suggestion. Read the file, run the command, check the output. "It should work" is not evidence.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 869-Item Review Checklist
One file, 71 categories: correctness, security, error handling, concurrency, data integrity, observability, accessibility, performance budgets, supply chain. Apply by category, not by ceremony.

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
| [`CLAUDE.md`](CLAUDE.md) + [`rules/`](rules) | Always-on engineering rules, tone, anti-hallucination, verification gates | Every conversation |
| [`standards/`](standards) + [`rules/index.yml`](rules/index.yml) | Domain expertise that loads on trigger keywords | When the task needs it |
| [`hooks/`](hooks) | Runtime blocks for destructive commands, secrets, banned patterns | Before every tool call |
| [`skills/`](skills) | Documented multi-step workflows: ship, review, plan, audit | When the user invokes `/<name>` |
| [`agents/`](agents) | Specialized subagents for focused review tasks | When delegated explicitly |
| [`checklists/`](checklists) | 869-item review checklist for code, infra, and process | On demand during review |

## What's Included

### Rules, always loaded

19 rules in [`rules/`](rules/), loaded into every conversation.

| Rule | What it covers |
|:-----|:---------------|
| [`architecture-defaults`](rules/architecture-defaults.md) | Five-question architecture gate. Forces DDD, hexagonal, idempotency, dedup, and state-machine standards to load when the task warrants them. Hard rules baseline |
| [`code-style`](rules/code-style.md) | DRY/SOLID/KISS, immutability, error classification, branded types, completeness rule |
| [`design-philosophy`](rules/design-philosophy.md) | Complexity manifestations and root causes, deep modules, strategic vs tactical, design it twice, red flags, design taste |
| [`testing`](rules/testing.md) | Integration-first, strict mock policy, AAA pattern, fake data, deterministic tests |
| [`security`](rules/security.md) | Secrets, auth, encryption, data privacy, audit logging, supply chain |
| [`git-workflow`](rules/git-workflow.md) | Conventional commits, branches, CI monitoring, PRs |
| [`verification`](rules/verification.md) | Evidence-based completion gates, response self-check |
| [`writing-precision`](rules/writing-precision.md) | Precision gate for all text output, plus pronoun discipline, active voice, and tone calibration with Claude-conversation examples |
| [`normative-keywords`](rules/normative-keywords.md) | BCP 14 (RFC 2119 + RFC 8174) keyword glossary. Lowercase primary, uppercase opt-in for critical correctness, security, data integrity, and irreversibility |
| [`repo-analysis`](rules/repo-analysis.md) | Clone external repos to a temp directory instead of fetching files via `gh`/raw URLs. Mandatory shallow-clone workflow, carve-outs for issue/PR/search ops, subagent briefing |
| [`pre-flight`](rules/pre-flight.md) | Duplicate check, market research, architecture fit, interface verification |
| [`surgical-edits`](rules/surgical-edits.md) | Every changed line traces to the request |
| [`ai-guardrails`](rules/ai-guardrails.md) | AI output review, plan before generating, multi-agent validation |
| [`memory-supersede`](rules/memory-supersede.md) | Supersede-not-delete for project and feedback memories |
| [`language`](rules/language.md) | Response language enforcement: all output in English |
| [`smart-questions`](rules/smart-questions.md) | Question format, mandatory recommendation when presenting a choice, status reports, FIXED/RESOLVED/DONE loop closure, Tatham bug-report essentials |
| [`found-fix`](rules/found-fix.md) | Any verification-surface finding is in scope for the current task. Bans the rationalization phrases that defer fixes to a later session |
| [`no-ai-process-leak`](rules/no-ai-process-leak.md) | Blocks phase-N markers, plan-path references, hyperbole tells from commit messages and PR descriptions |
| [`markdown-links`](rules/markdown-links.md) | Every file mention in published markdown is a clickable link. Validator and PreToolUse hook enforce |
| [`living-specs`](rules/living-specs.md) | Non-trivial changes maintain a `specs/current/` living behavioral spec: requirements, Given/When/Then scenarios, ADDED/MODIFIED/REMOVED deltas, and a close-out merge that folds a completed change into the spec |

Plus 7 language-specific files in [`rules/lang/`](rules/lang/): `typescript-immutability`, `typescript-types`, `typescript-strict`, `prisma-migrations`, `typeorm-migrations`, `drizzle-migrations`, `sequelize-migrations`.

### Standards, loaded on demand

65 standards in [`standards/`](standards/). Each entry in [`rules/index.yml`](rules/index.yml) declares trigger keywords. When a task matches, only those standards load.

Topics: API design, authentication, caching, code review, container security, contract testing, database, DDD, debugging, distributed systems, documentation, frontend, GraphQL, hexagonal architecture, i18n, infrastructure, low-latency engineering, message queues, mobile, monorepo, observability, OpenTelemetry, performance, postgres, privacy, redis, resilience, secrets management, SRE, state machines, twelve-factor, TypeScript 5.x, WebSocket, zero-downtime deployments, and more.

### Skills

33 skills in [`skills/`](skills/). Each is a folder with a `SKILL.md` that documents steps, output format, and rules.

| Skill | What it does |
|:------|:-------------|
| [`/ship`](skills/ship/SKILL.md) | Delivery pipeline: commit, PR, release, CI checks, worktrees |
| [`/review`](skills/review/SKILL.md) | Three-pass code review, QA analysis, visual audit |
| [`/respond`](skills/respond/SKILL.md) | Handle incoming review comments: classify, verify, draft replies, validate locally, post, resolve, monitor CI |
| [`/assessment`](skills/assessment/SKILL.md) | Architecture completeness audit. Finds missing patterns, planted defects, and standout opportunities. Outputs a machine-readable findings table that `/respond` can consume |
| [`/plan`](skills/plan/SKILL.md) | Spec folders with discovery, scope review, ADRs, scaffolding |
| [`/audit`](skills/audit/SKILL.md) | Security audit, threat modeling, supply chain checks. `/audit trust` adds untrusted-project safety scanning with IOC catalog at [`trust-patterns.md`](skills/audit/trust-patterns.md) |
| [`/test`](skills/test/SKILL.md) | Test execution, perf, lint, CI smoke, stub generation |
| [`/deploy`](skills/deploy/SKILL.md) | Post-merge landing and canary monitoring |
| [`/investigate`](skills/investigate/SKILL.md) | Systematic debugging with hypothesis testing, 3-strike limit |
| [`/research`](skills/research/SKILL.md) | Multi-source research with entity resolution and citation discipline |
| [`/design`](skills/design/SKILL.md) | Design consultation, variants, design-system work |
| [`/refactor`](skills/refactor/SKILL.md) | Guided refactoring with behavior preservation |
| [`/migrate`](skills/migrate/SKILL.md) | Framework or library migration with incremental testing |
| [`/infra`](skills/infra/SKILL.md) | Container orchestration, IaC, database migrations |
| [`/hotfix`](skills/hotfix/SKILL.md) | Emergency production fix with expedited workflow |
| [`/incident`](skills/incident/SKILL.md) | Incident context gathering, blameless postmortem |
| [`/resolve`](skills/resolve/SKILL.md) | Merge conflict resolution with verification |
| [`/cleanup`](skills/cleanup/SKILL.md) | Stale branch, PR, and worktree cleanup |
| [`/checkpoint`](skills/checkpoint/SKILL.md) | Save and resume state across sessions |
| [`/explain`](skills/explain/SKILL.md) | Code explanation with Mermaid diagrams |
| [`/fix-issue`](skills/fix-issue/SKILL.md) | Fix a GitHub issue by number with tests |
| [`/guard`](skills/guard/SKILL.md) | Directory freeze and scope enforcement |
| [`/benchmark`](skills/benchmark/SKILL.md) | Performance regression detection with baselines |
| [`/profile`](skills/profile/SKILL.md) | N+1 queries, missing indexes, complexity hot spots |
| [`/onboard`](skills/onboard/SKILL.md) | Codebase onboarding: architecture map, "Start Here". Phase 0 prompts before running the trust scan. Flags `--trust` and `--verify` pre-decide non-interactively |
| [`/gan`](skills/gan/SKILL.md) | Generator-Evaluator iteration loop for building features against a scored rubric. Iterates planner, generator, and evaluator subagents until the threshold is met |
| [`/pr-summary`](skills/pr-summary/SKILL.md) | PR summary with reviewer suggestions |
| [`/readme`](skills/readme/SKILL.md) | README generation from codebase analysis |
| [`/retro`](skills/retro/SKILL.md) | Session retrospective with pattern extraction |
| [`/session-log`](skills/session-log/SKILL.md) | Session activity logger for handoff |
| [`/setup`](skills/setup/SKILL.md) | Interactive project environment setup |
| [`/tdd`](skills/tdd/SKILL.md) | Test-driven development loop. Vertical slices, no horizontal write-tests-then-all-impl |
| [`/zoom-out`](skills/zoom-out/SKILL.md) | Step back from tactical work to strategic view |
| [`/spike`](skills/spike/SKILL.md) | Throwaway artifact that answers one design question, two routes (state-branch terminal program, view-branch side-by-side variations) |
| [`/module-audit`](skills/module-audit/SKILL.md) | Codebase audit for shallow modules with before-and-after Mermaid recommendations and deletion-test classification |
| [`/concise-mode`](skills/concise-mode/SKILL.md) | Opt-in terse-reply mode. Drops filler and pleasantries while preserving code blocks, error strings, and destructive-action confirmations |

### Hooks

58 hooks in [`hooks/`](hooks/) wired through [`settings.json`](settings.json). Each runs before, after, or around a tool call.

**Bypass channels.** Every hook supports two. Either grants a pass; both coexist.

1. Parent-shell env var `<NAME>_DISABLE=1` (set before launching Claude Code).
2. In-session file registry `~/.claude/.bypass-state.json`. Engage from a live session via `python scripts/bypass.py set <hook> --ttl 600 --reason "<why>"`; clear with `python scripts/bypass.py clear [<hook>]`; inspect with `list`. TTL clamps to [60, 3600] seconds; the 60-minute ceiling is intentional so a forgotten bypass cannot stick. Wildcard entries (`set "*"`) short-circuit every hook until expiry, with a tighter default TTL of 5 minutes. File mode is 0600. See [`hooks/_lib/bypass.py`](hooks/_lib/bypass.py).

**Block-message schema.** New hooks render their stderr through [`hooks/_lib/output.py`](hooks/_lib/output.py) `block(...)`. Five sections in fixed order (`What was detected`, `Why this rule exists`, `How to fix`, `If the rule does not apply here`, `Decision guidance for Claude`), one of four decision verbs (`STOP-AND-ASK`, `FIX-AND-RETRY`, `BYPASS-ONCE`, `BYPASS-WITH-REASON`), both bypass channels named in every message. Validator at `output.validate_block_message(...)`. See [`hooks/large-file-blocker.py`](hooks/large-file-blocker.py) for a worked example.

| Hook | Trigger | What it does |
|:-----|:--------|:-------------|
| [`ai-attribution-blocker.py`](hooks/ai-attribution-blocker.py) | PreToolUse Bash/Write/Edit | Blocks AI co-author trailers in commits and PRs |
| [`ai-process-leak-blocker.py`](hooks/ai-process-leak-blocker.py) | PreToolUse Bash/Write/Edit | Blocks AI-process language in commits, PRs, release notes, and code comments. Catches phase-N markers, plan-path references, and hyperbole tells |
| [`as-any-blocker.py`](hooks/as-any-blocker.py) | PreToolUse Write/Edit | Blocks TypeScript `as any` and generic `any` |
| [`aws-profile-guard.py`](hooks/aws-profile-guard.py) | PreToolUse Bash | Blocks `aws configure set` without `--profile` |
| [`banned-phrases-blocker.py`](hooks/banned-phrases-blocker.py) | PreToolUse Bash/Write/Edit | Blocks conversational fluff and tactical hyperbole in PRs and docs |
| [`banned-prose-chars.py`](hooks/banned-prose-chars.py) | PreToolUse Write/Edit/Bash | Blocks em dashes, parens in prose, emojis, ASCII art |
| [`bulk-resolve-blocker.py`](hooks/bulk-resolve-blocker.py) | PreToolUse Bash | Blocks multi-thread `resolveReviewThread` loops on GitHub or GitLab |
| [`compact-context-saver.py`](hooks/compact-context-saver.py) | SessionStart / PreCompact / PostCompact | Preserves git status across compaction |
| [`config-protection.py`](hooks/config-protection.py) | PreToolUse Write/Edit/MultiEdit | Blocks edits to linter, formatter, and typechecker configs like tsconfig, eslint, ruff, mypy. Forces fixing code instead of weakening config |
| [`console-log-blocker.py`](hooks/console-log-blocker.py) | PreToolUse Write/Edit | Blocks `console.*` in non-test code |
| [`conventional-commits.py`](hooks/conventional-commits.py) | PreToolUse Bash | Validates conventional commit format |
| [`dangerous-command-blocker.py`](hooks/dangerous-command-blocker.py) | PreToolUse Bash | 150+ patterns: destructive shell commands, reverse shells, cloud deletions, IaC destroy |
| [`docker-context-guard.py`](hooks/docker-context-guard.py) | PreToolUse Bash | Forces `--context` or `DOCKER_CONTEXT` per call |
| [`dockerfile-compose-quality.py`](hooks/dockerfile-compose-quality.py) | PreToolUse Write/Edit/MultiEdit | Blocks `.env` and key/cert copies, secret-named `ENV`/`ARG` with literal values, Compose `privileged: true`, and host-namespace toggles. Warns on floating tags, `USER root`, deprecated top-level `version:`, and literal secrets in `environment:`. Bypass `DOCKERFILE_QUALITY_DISABLE=1` |
| [`drizzle-raw-sql-blocker.py`](hooks/drizzle-raw-sql-blocker.py) | PreToolUse Write/Edit | Blocks Drizzle raw query escape hatches |
| [`drizzle-schema-sync.py`](hooks/drizzle-schema-sync.py) | PreToolUse Write/Edit | Enforces Drizzle schema vs migration parity |
| [`english-only-reminder.py`](hooks/english-only-reminder.py) | UserPromptSubmit | Injects system-reminder forcing English assistant output |
| [`env-file-guard.py`](hooks/env-file-guard.py) | PreToolUse Write/Edit | Blocks edits to `.env`, private keys, cloud creds, tfstate |
| [`force-push-during-review.py`](hooks/force-push-during-review.py) | PreToolUse Bash | Blocks history-rewriting pushes when a `CHANGES_REQUESTED` review is open |
| [`found-fix-rationalization-blocker.py`](hooks/found-fix-rationalization-blocker.py) | PreToolUse Bash/Write/Edit | Blocks rationalization phrases that defer verification-surface findings to a later session. Targets commit messages, PR bodies, release notes, and code comments |
| [`gateguard-fact-force.py`](hooks/gateguard-fact-force.py) | PreToolUse Write/Edit/MultiEdit | Forces reading a file before the first edit per session unless the user named the path. Operationalizes the pre-flight "Confidence" rule |
| [`gcloud-config-guard.py`](hooks/gcloud-config-guard.py) | PreToolUse Bash | Forces `--configuration` per call |
| [`gh-run-watch-blocker.py`](hooks/gh-run-watch-blocker.py) | PreToolUse Bash | Blocks `gh run watch` and equivalents that poll every 3s and burn the API rate budget. Bypass `GH_RUN_WATCH_DISABLE=1` |
| [`gh-token-guard.py`](hooks/gh-token-guard.py) | PreToolUse Bash | Requires inline `GH_TOKEN`, blocks `gh auth switch` |
| [`repo-fetch-blocker.py`](hooks/repo-fetch-blocker.py) | PreToolUse Bash | Blocks per-file source fetching via `gh api .../contents`, `gh repo view <o>/<r> <path>`, `glab api .../repository/files`, and `raw.githubusercontent.com` curl/wget. Forces a shallow clone instead. Bypass `REPO_FETCH_DISABLE=1` |
| [`git-author-guard.py`](hooks/git-author-guard.py) | PreToolUse Bash | Blocks commits with unresolved identity or placeholder authors |
| [`glab-token-guard.py`](hooks/glab-token-guard.py) | PreToolUse Bash | Requires inline `GITLAB_TOKEN`, blocks GitLab auth login |
| [`interactive-cmd-blocker.py`](hooks/interactive-cmd-blocker.py) | PreToolUse Bash | Blocks `cp`/`mv`/`rm` without `-f`. macOS aliases these to `-i`, which hangs the agent on confirmation prompts. Bypass `INTERACTIVE_CMD_DISABLE=1` |
| [`internal-config-leakage.py`](hooks/internal-config-leakage.py) | PreToolUse Bash/Write/Edit | Prevents internal config references in external output |
| [`kubectl-context-guard.py`](hooks/kubectl-context-guard.py) | PreToolUse Bash | Forces `--context` or `KUBECONFIG` per call |
| [`large-file-blocker.py`](hooks/large-file-blocker.py) | PreToolUse Bash | Blocks commits with files over 5MB |
| [`markdown-link-discipline.py`](hooks/markdown-link-discipline.py) | PreToolUse Write/Edit/MultiEdit | Blocks new bare file mentions in markdown when the path resolves to a real repo file |
| [`mcp-health-check.py`](hooks/mcp-health-check.py) | PreToolUse/PostToolUse `mcp__*` | Tracks MCP server health in `cache/mcp-health.json`. Short-circuits calls to servers past the unhealthy-failure threshold |
| [`migration-idempotency.py`](hooks/migration-idempotency.py) | PreToolUse Write/Edit | Forces `IF NOT EXISTS` / `IF EXISTS` on DDL |
| [`mise-global-guard.py`](hooks/mise-global-guard.py) | PreToolUse Bash | Blocks `mise use --global`, forces project-local config |
| [`mock-internal-blocker.py`](hooks/mock-internal-blocker.py) | PreToolUse Write/Edit | Blocks mocking own services, DB, Redis, queues in tests |
| [`mutation-method-blocker.py`](hooks/mutation-method-blocker.py) | PreToolUse Write/Edit/MultiEdit | Blocks 90+ in-place mutation patterns in JS/TS |
| [`normative-keyword-discipline.py`](hooks/normative-keyword-discipline.py) | PreToolUse Write/Edit/MultiEdit | Blocks bullet items starting with `Should ` or `should ` in rules, standards, checklists, and [`CLAUDE.md`](CLAUDE.md). Enforces the BCP 14 weasel-words rule. Bypass `NORMATIVE_KEYWORD_DISABLE=1` |
| [`notify-webhook.py`](hooks/notify-webhook.py) | Stop | POST to `CLAUDE_NOTIFY_WEBHOOK` on response completion |
| [`prisma-raw-sql-blocker.py`](hooks/prisma-raw-sql-blocker.py) | PreToolUse Write/Edit | Blocks Prisma raw query escape hatches |
| [`prisma-schema-sync.py`](hooks/prisma-schema-sync.py) | PreToolUse Write/Edit | Enforces schema.prisma vs migration parity |
| [`read-injection-scanner.py`](hooks/read-injection-scanner.py) | PostToolUse Read/WebFetch/WebSearch | Scans fetched content for prompt-injection patterns (instruction override, tool redirection, authority claims, base64 runs, unicode confusables) and emits a warning. Bypass `READ_INJECTION_DISABLE=1` |
| [`redis-atomicity.py`](hooks/redis-atomicity.py) | PreToolUse Write/Edit | Forces atomic Redis sequences via Lua/MULTI |
| [`retro-pointer.py`](hooks/retro-pointer.py) | Stop | One-line summary at session end when blocks accumulated |
| [`review-state-guard.py`](hooks/review-state-guard.py) | PreToolUse Bash | Blocks accidental REQUEST_CHANGES, DISMISS, or DELETE on reviews not authored by the user |
| [`rtk-rewrite.py`](hooks/rtk-rewrite.py) | PreToolUse Bash | Rewrites CLI commands through RTK for token savings |
| [`scope-guard.py`](hooks/scope-guard.py) | PreToolUse Write/Edit/MultiEdit | Reads the most recent active `specs/*/plan.md` (modified within 60min). Asks confirmation when the edit target is not in the plan's declared file list. Bypass `SCOPE_GUARD_DISABLE=1` |
| [`secret-scanner.py`](hooks/secret-scanner.py) | PreToolUse Bash | 40+ secret patterns before git commit |
| [`sequelize-raw-sql-blocker.py`](hooks/sequelize-raw-sql-blocker.py) | PreToolUse Write/Edit | Blocks Sequelize raw query escape hatches |
| [`sequelize-schema-sync.py`](hooks/sequelize-schema-sync.py) | PreToolUse Write/Edit | Enforces Sequelize model vs migration parity |
| [`session-resume-context.py`](hooks/session-resume-context.py) | SessionStart | Surfaces the most recent checkpoint or active spec plan (within 7 days) as `additionalContext` on startup, clear, or compact so the session resumes with a pointer to in-progress work |
| [`settings-hygiene.py`](hooks/settings-hygiene.py) | PreToolUse Write/Edit/MultiEdit | Blocks credentials and absolute home paths in settings |
| [`smart-formatter.py`](hooks/smart-formatter.py) | PostToolUse Edit/Write | Auto-formats: prettier, black, gofmt, rustfmt, shfmt. Batches files for the Stop hook |
| [`stop-format-typecheck.py`](hooks/stop-format-typecheck.py) | Stop | Reads the batched edit list from `smart-formatter.py`, deduplicates, formats once, then runs typecheck once per touched workspace |
| [`subagent-brief-quality.py`](hooks/subagent-brief-quality.py) | PreToolUse Task | Enforces subagent prompt quality with shape, file references, and length cap |
| [`tdd-gate.py`](hooks/tdd-gate.py) | PreToolUse Write/Edit/MultiEdit | Blocks creation of a new production source file when no companion test file can be located. Bypass `TDD_GATE_DISABLE=1` |
| [`terraform-workspace-guard.py`](hooks/terraform-workspace-guard.py) | PreToolUse Bash | Forces `TF_WORKSPACE` per call |
| [`todo-marker-blocker.py`](hooks/todo-marker-blocker.py) | PreToolUse Write/Edit/MultiEdit | Blocks TODO/FIXME/HACK/XXX/WIP markers in source code, allows issue-linked form `TODO(#123)` |
| [`typeorm-raw-sql-blocker.py`](hooks/typeorm-raw-sql-blocker.py) | PreToolUse Write/Edit | Blocks TypeORM raw query escape hatches |
| [`typeorm-schema-sync.py`](hooks/typeorm-schema-sync.py) | PreToolUse Write/Edit | Enforces TypeORM entity vs migration parity |

### Custom Agents

15 specialized subagents in [`agents/`](agents/). Each follows the agent template at [`TEMPLATE.md`](agents/TEMPLATE.md) and inherits shared discipline from [`_shared-principles.md`](agents/_shared-principles.md).

| Agent | Purpose |
|:------|:--------|
| [`accessibility-auditor`](agents/accessibility-auditor.md) | WCAG 2.1 AA accessibility review |
| [`api-reviewer`](agents/api-reviewer.md) | API backward compatibility and design review |
| [`blast-radius`](agents/blast-radius.md) | Trace all consumers of changed interfaces |
| [`conversation-analyzer`](agents/conversation-analyzer.md) | Read a session transcript and surface patterns worth capturing as instincts, hooks, or rule revisions |
| [`documentation-checker`](agents/documentation-checker.md) | Documentation accuracy vs codebase |
| [`gan-planner`](agents/gan-planner.md) | First step of the `/gan` loop. Expands a brief into acceptance criteria, a file list, and a five-row scoring rubric |
| [`gan-generator`](agents/gan-generator.md) | Second step of the `/gan` loop. Implements the plan against the named files. Returns proposed diffs, never writes |
| [`gan-evaluator`](agents/gan-evaluator.md) | Third step of the `/gan` loop. Scores the implementation against the planner's rubric. Returns per-row scores and concrete feedback |
| [`i18n-validator`](agents/i18n-validator.md) | Translation file validation |
| [`migration-planner`](agents/migration-planner.md) | Database migration safety and ordering |
| [`opensource-sanitizer`](agents/opensource-sanitizer.md) | Pre-public-push safety net. Scans diffs for leaked secrets, PII, internal references, and other artifacts that should not appear in a public repository |
| [`red-team`](agents/red-team.md) | Adversarial analysis: attack happy paths |
| [`scope-drift-detector`](agents/scope-drift-detector.md) | Compare diff against plan for scope drift |
| [`test-scenario-generator`](agents/test-scenario-generator.md) | Test scenarios with priority and traceability |
| [`type-design-analyzer`](agents/type-design-analyzer.md) | Review TypeScript type design for encapsulation, invariant expression, and runtime safety |

### Workflow Decision Guide

Pick the skill by what you are trying to do, not by what the skill is called. Scenarios are grouped by intent. When two skills could apply, the final subsection shows how to pick.

#### Building, planning, and prototyping

| Scenario | Start with |
|:---------|:-----------|
| "I need to build X" | `/plan --discover` then implement |
| "Think through this before coding" | `/plan` |
| "Record an architecture decision" | `/plan adr new <title>` |
| "Generate boilerplate matching project patterns" | `/plan scaffold <type> <name>` |
| "Set up this project for the first time" | `/setup` |
| "Spin up Docker or database for local dev" | `/infra docker` or `/infra db` |
| "First-time codebase walkthrough" | `/onboard` |
| "Write the test first, then code" | `/tdd` |
| "Explain how this code works" | `/explain` |
| "I am lost in unfamiliar code" | `/zoom-out` |

#### Reviewing, validating, and responding

| Scenario | Start with |
|:---------|:-----------|
| "Review this PR" | `/review <PR>` |
| "Review my local branch before pushing" | `/review --local` |
| "Test coverage gaps and QA scenarios" | `/review qa` |
| "Accessibility, performance, SEO audit on the UI" | `/review design` |
| "Run tests, coverage, lint, build" | `/test` |
| "Load test or HTTP perf benchmark" | `/test perf` |
| "Design consultation before implementing UI" | `/design` |
| "Generate UI design variants for comparison" | `/design variants` |
| "Reviewer left comments on my PR" | `/respond` |
| "Pre-submission audit or take-home check" | `/assessment` |
| "Find what is missing the way an interviewer would" | `/assessment --focus <area>` |
| "Summarize this PR for reviewers" | `/pr-summary` |
| "Are we secure" | `/audit` |
| "Threat model or STRIDE analysis" | `/audit cso` |
| "Dependency vulnerability scan" | `/audit deps` |

#### Shipping and delivery

| Scenario | Start with |
|:---------|:-----------|
| "Commit and push" | `/ship commit --push` |
| "Open a PR" | `/ship pr` |
| "Create a tagged release" | `/ship release` |
| "Is my code ready to ship" | `/review --local` then `/ship` |
| "CI is failing" | `/ship checks` |
| "Watch CI to green and address AI bot threads" | `/ship commit --pipeline` |
| "Land the PR after approval" | `/deploy land` |
| "Canary deploy and monitor" | `/deploy canary` |
| "Parallel work across branches" | `/ship worktree init` |

#### Debugging and incident response

| Scenario | Start with |
|:---------|:-----------|
| "Something is broken" | `/investigate` |
| "Why is this slow" | `/profile` |
| "Performance regression vs baseline" | `/benchmark` |
| "Prod is broken, fix NOW" | `/hotfix` |
| "Write a postmortem" | `/incident` |
| "Fix a GitHub issue by number" | `/fix-issue <number>` |

#### Refactoring and migration

| Scenario | Start with |
|:---------|:-----------|
| "This code needs restructuring" | `/refactor` |
| "Upgrade framework or library version" | `/migrate` |
| "Replace library A with library B" | `/migrate` |
| "Resolve merge conflicts" | `/resolve` |

#### Documentation and discovery

| Scenario | Start with |
|:---------|:-----------|
| "Write or update a README" | `/readme` |
| "Generate an assessment-style README" | `/readme --variant assessment` |
| "What does the community say about X" | `/research X` |
| "X vs Y, which is better" | `/research X vs Y` |
| "Find prior art for an idea" | `/research <topic>` |

#### Operations and housekeeping

| Scenario | Start with |
|:---------|:-----------|
| "Clean up stale branches, PRs, and worktrees" | `/cleanup` |
| "Save session state to resume later" | `/checkpoint save` |
| "Resume where I left off" | `/checkpoint resume` |
| "Lock down before a risky operation" | `/guard` |
| "Standup or handoff notes" | `/session-log` |
| "Session retrospective" | `/retro` |
| "Discover codebase patterns and extract rules" | `/retro discover` |

#### Recurring and scheduled work

| Scenario | Start with |
|:---------|:-----------|
| "Poll something every N minutes" | `/loop <interval> /<command>` |
| "Self-paced repeat of a task" | `/loop /<command>` |
| "Cron-style scheduled remote agent" | `/schedule` |

#### When two skills could apply

| Ambiguity | Choose | Because |
|:----------|:-------|:--------|
| `/review` vs `/assessment` | `/review` for diff-level findings; `/assessment` for whole-system audit | `/review` catches bugs in what was written; `/assessment` finds patterns that should be present but are not |
| `/review` vs `/audit` | `/audit` for security focus; `/review` for general quality | `/audit` runs STRIDE, dependency scans, and secret detection; `/review` runs the 71-category checklist |
| `/respond` vs `/ship --pipeline` | `/respond` for human reviewer threads; `/ship --pipeline` for unattended AI-bot threads | Set `RESPOND_DRIVES_PIPELINE=1` to delegate the bot loop to `/respond` and unify the vocabulary across both flows |
| `/investigate` vs `/profile` | `/investigate` for correctness; `/profile` for performance | `/investigate` debugs why something fails; `/profile` finds bottlenecks in working code |
| `/refactor` vs `/migrate` | `/refactor` for internal restructure; `/migrate` for framework or version change | `/refactor` preserves behavior in your own code; `/migrate` follows the upstream's official upgrade docs |
| `/explain` vs `/onboard` | `/explain` for a single file or function; `/onboard` for a whole project | `/explain` traces data flow with Mermaid; `/onboard` produces a "start here" guide with architecture map |
| `/explain` vs `/zoom-out` | `/explain` for "what does this do"; `/zoom-out` for "where does this fit" | `/explain` goes deep into one piece; `/zoom-out` traces callers and surfaces the architectural role |
| `/loop` vs `/schedule` | `/loop` for one terminal session; `/schedule` for a remote cron-style agent | `/loop` self-paces or polls inside the current session; `/schedule` runs an agent on a server on a recurring schedule |
| `/cleanup` vs `/refactor` | `/cleanup` for git artifacts; `/refactor` for code quality | `/cleanup` deletes stale branches, PRs, worktrees; `/refactor` improves code structure without changing behavior |
| `/test` vs `/review qa` | `/test` to execute; `/review qa` to analyze | `/test` runs the test suite, coverage, lint, perf; `/review qa` finds coverage gaps and writes scenarios |

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

36 MCP servers wired in [`settings.json`](settings.json) across three transports:

- **Stdio, no env:** Playwright, Memory, Sequential Thinking, Docker, Lighthouse, Ollama, Filesystem
- **Stdio with env:** GitHub, GitLab, PostgreSQL, Redis, Slack, Obsidian, Kubernetes, AWS, Cloudflare, Puppeteer, Brave Search, Google Maps, Firecrawl, Resend, Todoist, Discord, Perplexity, LangSmith, Semgrep, Qdrant
- **Remote HTTP, zero startup:** Sentry, Linear, Figma, Notion, Vercel, Supabase, Atlassian, Mermaid Chart, Asana

### Permissions

- **76 deny rules** protect sensitive files: `.env` variants, SSH keys, AWS creds, GnuPG, `*.pem`, `*.key`, `*.tfstate`, `node_modules`
- **21 allow rules** enable read-only operations without prompting: `git diff`, `git log`, `git status`, `pnpm run`, `npx`

The `env-file-guard.py` hook adds a runtime layer that catches anything permissions miss.

<details>
<summary><strong>Project structure</strong></summary>

```
$HOME/.claude/
  CLAUDE.md              Core engineering rules, always loaded
  RTK.md                 RTK token-optimized CLI proxy reference
  settings.json          Permissions, hooks, MCP servers
  checklists/            Unified 869-item review checklist across 71 categories
  rules/                 17 always-on rules plus 7 language-specific
    index.yml            Rule and standard catalog with trigger keywords
    lang/                TypeScript, Prisma, TypeORM, Drizzle, Sequelize rules
  standards/             65 on-demand domain standards
  agents/                15 specialized subagents
  skills/                33 slash-command skills
    audit/trust-patterns.md  IOC catalog for the /audit trust scan
  hooks/                 52 runtime hooks
  .github/scripts/       Validation and maintenance scripts (CI helpers)
  hooks/_lib/            Shared hook libraries (mutation detectors, audit log, suppression)
  tests/                 Hook smoke tests and fixture trees
  .github/workflows/     Lint, validation, hook tests
```

</details>

## FAQ

<details>
<summary><strong>How do I customize or disable a rule?</strong></summary>
<br>

Rules in [`rules/`](rules) load into context automatically. To disable one, delete or rename the file. To customize, edit the markdown. Changes take effect on the next conversation.

</details>

<details>
<summary><strong>How do I add a new skill?</strong></summary>
<br>

Create a directory under [`skills/`](skills) with a `SKILL.md` file. Use frontmatter: `name`, `description` for trigger matching, then the skill body with steps and rules. See any existing skill for the shape.

</details>

<details>
<summary><strong>Why integration tests over unit tests?</strong></summary>
<br>

The testing rule treats unit tests as a fallback for pure functions. A test that mocks the database may pass while the actual query is broken. The mock proves the mock works, not the code. See [`rules/testing.md`](rules/testing.md).

</details>

<details>
<summary><strong>How does two-tier rule loading save context?</strong></summary>
<br>

The 63 standards total roughly 12,000 lines. Loading all of them into every conversation would burn the context window. [`rules/index.yml`](rules/index.yml) maps each standard to trigger keywords. When a task matches, e.g. "add a database migration" pulls `database.md`, only the relevant standards load. Most conversations need 2-5 standards.

</details>

<details>
<summary><strong>What does the dangerous command blocker cover?</strong></summary>
<br>

150+ patterns: filesystem destruction, privilege escalation, reverse shells, git destructive operations, AWS/GCP/Azure CLI deletions, Vercel/Netlify/Firebase, Docker and Kubernetes destructive commands, database CLI drops, IaC destroy, SQL statements without WHERE, credential exfiltration.

</details>

## License

[MIT](LICENSE)

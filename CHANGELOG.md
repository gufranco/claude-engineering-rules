# Changelog

All notable changes to this Claude Code configuration are documented here.

## 2026-05-21

### Added

- Global markdown link discipline. New rule at [`rules/markdown-links.md`](rules/markdown-links.md) codifies the convention that every file mention in published markdown is a clickable link to the actual file. Registered in [`rules/index.yml`](rules/index.yml) under `always_loaded`. Generalizes the README-only rule that previously lived in [`skills/readme/SKILL.md`](skills/readme/SKILL.md). Two acceptable forms: `[file.ext](file.ext)` and `` [`file.ext`](file.ext) ``.
- [`scripts/markdown_link_detector.py`](scripts/markdown_link_detector.py): shared detection module used by both the validator and the hook so they cannot drift. Detects backticked tokens whose path resolves to an existing repo file and which are not wrapped in a markdown link. Skip-list for [`tests/`](tests/), [`scripts/`](scripts/), [`.github/`](.github/), `tools/`, and [`specs/`](specs/). The [`specs/`](specs/) tree is advisory only.
- [`scripts/validate-markdown-links.py`](scripts/validate-markdown-links.py): CI validator. Scans every tracked `.md` file. Exit 1 on any bare reference to an existing repo file. Wired into the Lint job in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
- [`scripts/fix-markdown-links.py`](scripts/fix-markdown-links.py): one-shot auto-wrapper used to apply the rule across legacy markdown. Applied 522 fixes across 100 files in this rollout.
- [`hooks/markdown-link-discipline.py`](hooks/markdown-link-discipline.py): PreToolUse Write or Edit or MultiEdit hook. Diff-aware: blocks only when the change introduces a NEW bare reference whose path resolves to a real file. Pre-existing bare references are not flagged, so legacy markdown can still be edited without triggering. Bypass via `MARKDOWN_LINKS_DISABLE=1`. Registered in [`settings.json`](settings.json).
- Tests at [`tests/hooks/markdown-link-discipline/`](tests/hooks/markdown-link-discipline/) and [`tests/scripts/test_validate_markdown_links.py`](tests/scripts/test_validate_markdown_links.py).

### Changed

- [`README.md`](README.md) regenerated with full link discipline. The Hooks table now lists all 44 hooks, previously 30 and incomplete, with each row linked to the actual `hooks/*.py` or `hooks/*.sh` file. The Skills table now links every `/<name>` row to the corresponding `skills/<name>/SKILL.md`. Stale `33 hooks` mentions in prose corrected to `44`. Sidebar metric and project-tree count brought into agreement with the actual file count.
- [`skills/readme/SKILL.md`](skills/readme/SKILL.md) "File References (MANDATORY)" section now points at the global rule instead of duplicating it. Becomes a 6-line quick reference.
- 100 other markdown files across [`rules/`](rules/), [`standards/`](standards/), [`skills/`](skills/), [`CLAUDE.md`](CLAUDE.md), and [`CHANGELOG.md`](CHANGELOG.md) had their bare file mentions auto-wrapped by the new fix script. Total: 522 references linked.

## 2026-05-20

### Added

- `/respond` skill: receive-side counterpart to `/review`. Fetches unresolved review threads from a PR you authored, classifies each by author type and Conventional Comments intent, verifies against the current code, drafts replies in a natural human voice, applies code changes through the local quality gate, posts replies, resolves threads, and monitors CI to green. Seven-phase pipeline with six supporting sections covering Service Level Expectations, AI Bot Triage Tactics, Multi-Reviewer Conflict Resolution, Resolution Convention, Commit Credit Conventions, plus a Ticket Tracker Integration section that auto-files deferred items into GitHub Issues, Linear, Jira, or GitLab Issues
- [`skills/respond/reply-templates.md`](skills/respond/reply-templates.md): 19 intent-by-decision cells with 3+ good and 3+ bad exemplars per cell. Drawn from canonical sources, independently authored
- [`skills/respond/bot-triage.md`](skills/respond/bot-triage.md): per-tool false-positive catalog for CodeRabbit, Greptile, Copilot, Cursor BugBot, Sourcery, Qodo Merge, Korbit. Command grammar reference, teach-once playbook, and per-tool default strategy
- [`skills/respond/platform-gitlab.md`](skills/respond/platform-gitlab.md): GitLab platform reference. Discussion model, glab CLI surface, REST API patterns, resolve semantics, AI bot allowlist for GitLab Duo, CodeRabbit on GitLab, Sourcery, Greptile
- [`skills/respond/platform-bitbucket.md`](skills/respond/platform-bitbucket.md): Bitbucket Cloud reference. REST API patterns via curl, app password and token auth, and the documented limitations vs GitHub including the absence of native thread resolution
- 3 new PreToolUse Bash hooks supporting the new workflow. `bulk-resolve-blocker` forbids multi-thread resolveReviewThread loops. `review-state-guard` forbids accidental REQUEST_CHANGES, DISMISS_REVIEW, DELETE on reviews not authored by the running user. `force-push-during-review` blocks force-push when a CHANGES_REQUESTED review is open on the current branch's PR. Each carries a bypass env var
- "As Reviewee" section in [`standards/code-review.md`](standards/code-review.md): 20 best practices grouped by Posture, Mechanics, Reply Form, Thread State, Scope, Triage, and Multi-Reviewer dynamics, plus 18 anti-patterns drawn from Google eng-practices, Tidyverse, GitLab handbook, Tatham's antipatterns catalogue, and other canonical sources
- `/assessment` skill restored from commit `d26fdb4~1` and improved with the same vocabulary as `/review` and `/respond`. Conventional Comments taxonomy mapping in the Classification section, Service Level awareness when assessing a PR, machine-readable findings table appended to the narrative report so `/respond` can parse the output, regression-test pinning recommendation for blocking findings, cross-link to `/respond` in Related skills. Em dashes throughout the restored file replaced with periods or colons to match current style
- `/assessment` gap-analysis pass: category count corrected from 69 to 70 across all references. Step 8 enumeration extended to cover categories 59 through 70 by name. Step 7 trait table extended with rows for time zones (59), money math (60), locales (61), regulated data (67), vendors (68), and ORM-managed schemas (69). The `--focus` block updated: `cost-optimization.md` renamed to `cost-awareness.md`; `event-driven-architecture.md` consolidated into `message-queues.md`; six dropped standards removed (`multi-tenancy.md`, `feature-flags.md`, `mlops.md`, `data-pipelines.md`, `grpc-services.md`, `serverless-edge.md`). Eight rule paths that migrated from [`rules/`](rules) to [`standards/`](standards) now point at the correct directory. References added to `rules/lang/typescript-*.md` and `rules/lang/*-migrations.md`. The `gh repo edit` example now uses the `GH_TOKEN=$(gh auth token --user <account>)` prefix per [`standards/multi-account-cli.md`](standards/multi-account-cli.md). Markdown numbering bug in the convergence loop section fixed (steps 11, 12, 13 instead of resetting to 1, 2, 3). Related skills extended to cross-reference Feedback Equation, AI Bot Triage, Multi-Reviewer Conflict, Ticket Tracker Integration, the GitLab and Bitbucket platform files, and the `As Reviewee` section of [`standards/code-review.md`](standards/code-review.md)
- README template consolidation: `skills/assessment/readme-template.md` moved to [`skills/readme/template-assessment.md`](skills/readme/template-assessment.md). `/readme` gained a `--variant <marketing|assessment>` flag, default marketing. The assessment variant uses the moved template; the marketing variant uses the structure documented inline in [`skills/readme/SKILL.md`](skills/readme/SKILL.md). `/assessment` step 12 now invokes `/readme --variant assessment` instead of reading a local template, so README structure has one owner across both flows. `/readme` description updated to reflect the two variants and drop the "do not use for assessment READMEs" exclusion
- `/readme` upgraded with research-backed 2025-2026 patterns. Hero section uses the `<picture>` light and dark logo pattern with `prefers-color-scheme` plus a pipe-separated navigation pill row (Docs, Discord, Twitter, Issues). Badges section gains a 5-to-8 cap, a high-signal allowlist with the OpenSSF Scorecard format, an explicit denylist of vanity badges, and alt-text reminders. Comparison tables now use plain `Yes` and `No` text instead of emoji for screen-reader accessibility. New sections added: 7c GitHub Alerts covering all five types (NOTE, TIP, IMPORTANT, WARNING, CAUTION) with use cases, 7d Sponsors and Backers with Platinum/Gold/Silver tier templates from pnpm and Biome, 7e AI Companion Files documenting the `llms.txt` and `AGENTS.md` conventions, 7f Multilingual Variants with the ISO 639-1 filename convention and a language switcher pattern. GitHub About section expanded with the 20-topic limit, 50-character per-topic constraint, lowercase-and-hyphens-only rule, and detailed Social Preview Image specifications (1280x640 PNG under 1 MB, 1200x630 cross-platform sweet spot). New Accessibility section covering alt text, 4.5:1 contrast, heading order, no color-only signaling. New Measurement section listing GitHub Insights, star-history.com, repohistory.com, and the conversion-ratio framework. New Anti-Patterns table with the 10 patterns that universally damage README impact. Three new rules added: 5-second test, badge cap, demo-first
- [`skills/readme/template-assessment.md`](skills/readme/template-assessment.md) extended with a "Trade-offs and What I Would Do With More Time" table for take-home submissions and an "Assumptions" section that surfaces non-obvious choices the reviewer would otherwise have to ask about
- Self-review-driven fixes: `bulk-resolve-blocker.py` rewritten to require an actual `gh api ... resolveReviewThread` or `glab api -X PUT ... resolved=true` call before counting, eliminating a false-positive that fired whenever a Bash command happened to mention `resolveReviewThread` alongside an unrelated loop. GitLab REST-style bulk resolves are now also detected. README hook count corrected to 43 in both the sidebar metric and the project-tree block. Docstrings on the three new hooks now document their GitHub-only or GitHub-plus-GitLab platform scope explicitly. [`.last-cleanup`](.last-cleanup) added to [`.gitignore`](.gitignore) to stop it from showing in `git status`

### Changed

- [`skills/review/SKILL.md`](skills/review/SKILL.md) gained 7 improvements: Conventional Comments taxonomy in posted comments, Feedback Equation guidance for pushback-anticipated comments, Service Level awareness in the verdict, multi-reviewer dynamics check before posting, standard shorthand vocabulary covering PTAL, LGTM, NIT, RFC, and WDYT, regression-test pinning recommendation, PR-author anti-pattern detection
- [`skills/readme/SKILL.md`](skills/readme/SKILL.md) gained a "For Contributors and Reviewers" subsection that lowers the cost of contribution by surfacing reproducing instructions, project conventions, non-obvious decisions, and the issue tracker link. Phase 1 Deep Scan extended to detect commit format, lint config, AI review bots, and issue tracker
- [`skills/ship/SKILL.md`](skills/ship/SKILL.md) Pipeline Monitoring intro now directs human-thread handling to `/respond`. Step 6 documents an opt-in delegation: with `RESPOND_DRIVES_PIPELINE=1` set, the AI-bot sweep delegates to `/respond --auto --include-bots` for unified vocabulary across both flows
- [`rules/index.yml`](rules/index.yml) `code-review` triggers extended with `respond, reply, address comments, incoming review, handle review, reviewer comments, pr feedback, reviewee, conventional comments, ptal, lgtm, nit`
- [`hooks/internal-config-leakage.py`](hooks/internal-config-leakage.py) skip list extended to include [`CHANGELOG.md`](CHANGELOG.md), since the changelog is the canonical place for config-path references
- [`README.md`](README.md) skill count 30 to 31, hook count 33 to 36, added `/respond` row to the skills table
- [`settings.json`](settings.json) registered the 3 new hooks in the PreToolUse Bash matcher chain

## 2026-05-01

### Added

- Hook block feedback loop: every blocking hook now emits a structured JSONL event to [`logs/hooks.log`](logs/hooks.log) via [`scripts/audit_log.py`](scripts/audit_log.py) (with secret redaction, file locking, and 5 MiB rotation). New `retro-pointer.py` Stop hook surfaces a one-line summary at session end when blocks accumulated. `/retro --hooks` mines the log to cluster repeat offenders and propose upstream fixes in rules, skills, or CLAUDE.md so the model self-corrects before the hook fires next time. Hook authoring standard updated with mandatory audit emission patterns for both Python and shell hooks
- Git author identity isolation: a per-remote identity resolution pattern in the user gitconfig via `includeIf "hasconfig:remote.*.url:..."` plus a `git-author-guard` PreToolUse hook that blocks commits with no resolved identity, env-injected author overrides, local `user.*` writes, and pushes carrying placeholder authors. Bypass via `GIT_AUTHOR_GUARD_DISABLE=1`
- New standard documenting the three-layer pattern (declarative gitconfig, defensive hook, documentary standard) with placeholder identities
- 10 new test fixtures and a dedicated section in the hook smoke test runner covering commit, push, and config mutation paths

## 2026-04-29

### Added

- Multi-account CLI safety: parallel terminals targeting different accounts no longer break when one terminal would have switched global state. 6 new PreToolUse hooks hard-block the global-mutation commands and force the per-command form: `docker-context-guard`, `kubectl-context-guard`, `aws-profile-guard`, `gcloud-config-guard`, `terraform-workspace-guard`, `mise-global-guard`
- [`standards/multi-account-cli.md`](standards/multi-account-cli.md): canonical doc for the per-command pattern across 8 CLIs (gh, glab, docker, kubectl, aws, gcloud, terraform workspace, mise) with detection order, anti-pattern table, and a recipe for adding new tools
- 30 new test fixtures covering blocked and allowed scenarios for every new hook

### Changed

- `gh-token-guard` and `glab-token-guard` error messages now point at [`standards/multi-account-cli.md`](standards/multi-account-cli.md)
- [`standards/borrow-restore.md`](standards/borrow-restore.md): rewritten for `mise`, the user's runtime version manager. mise resolves per-project from `.mise.toml`/`.tool-versions` and never mutates a shared "active version", so the borrow-restore fallback is no longer needed for any tool in the toolchain
- [`skills/setup`](skills/setup): detects mise via `.mise.toml`/`.tool-versions`/legacy compat files, runs `mise install` + `mise current` once before per-runtime checks
- [`skills/assessment`](skills/assessment): version manager and CI sections feature mise as Recommended; legacy nvm/asdf/pyenv accepted for compat

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

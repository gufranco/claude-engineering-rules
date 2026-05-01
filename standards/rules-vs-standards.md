# Rules vs Standards Taxonomy

How the two-tier configuration system in `~/.claude/` organizes guidance, and how to decide where new content belongs.

## The Two Tiers

| Tier | Directory | Loading | Token cost |
|------|-----------|---------|------------|
| Tier 1 | `rules/` | Always loaded into every conversation | Fixed, every session |
| Tier 2 | `standards/` | Loaded on demand when triggers match | Zero unless invoked |

Tier 1 content shapes how every response is produced. Tier 2 content provides domain-specific depth that only matters when the task touches that domain.

## Decision Matrix

Use this matrix to decide where new content belongs.

| Question | If yes → | If no → |
|----------|---------|---------|
| Does this apply to every task regardless of domain? | rules/ | standards/ |
| Would skipping this guidance cause harm in code I write today, even if the task is unrelated? | rules/ | standards/ |
| Is this guidance specific to one technology, framework, or workflow? | standards/ | rules/ |
| Does this guidance exceed 200 lines? | standards/ | either |
| Is the trigger set narrower than 10 keywords? | standards/ | rules/ |
| Is this a reference document the model only needs occasionally? | standards/ | not rules/ |

When two answers conflict: prefer standards/. The cost of an unloaded standard is one missed trigger. The cost of a loaded rule that does not apply is permanent token tax on every conversation.

## Tier 1 Membership Criteria

A file belongs in `rules/` only if it meets every criterion:

1. **Universal applicability.** The guidance shapes every coding task. Examples: error classification, surgical edits, response language, completion gates.
2. **Behavioral, not informational.** It tells the model what to do, not what something is. Standards reference material belongs in standards/.
3. **Token budget justified.** Loaded into every conversation, every turn. The cost must be worth it.
4. **No technology coupling.** Rules apply across languages, frameworks, and runtimes. Technology-specific guidance is a standard.
5. **Stable.** Rules change rarely. Frequent edits indicate the content is closer to a standard or a skill.

Current Tier 1 files: `code-style.md`, `git-workflow.md`, `language.md`, `pre-flight.md`, `surgical-edits.md`, `security.md`, `testing.md`, `verification.md`, `writing-precision.md`, `ai-guardrails.md`.

## Tier 2 Membership Criteria

A file belongs in `standards/` if any of the following hold:

1. **Domain-specific.** Applies only to a technology, framework, or workflow. Example: `postgresql.md`, `redis.md`, `rust.md`.
2. **Reference material.** A lookup the model consults rather than guidance it always carries. Example: `llm-docs.md`, `identifiers.md`.
3. **Optional depth.** Adds nuance beyond what `rules/` covers but is unnecessary for unrelated work.
4. **Trigger-friendly.** A clear keyword set identifies when the standard is needed.

## Trigger Design

Standards are loaded by matching task descriptions against the `triggers` field in `rules/index.yml`. Triggers must be:

- **Specific enough** to avoid loading the standard for unrelated tasks
- **General enough** to fire when the standard genuinely applies
- **Stable** across renaming and refactors of related code

| Anti-pattern | Why it fails | Fix |
|--------------|--------------|-----|
| Single-word triggers like `db` | Match too broadly, load standard for unrelated tasks | Use compound terms: `database schema`, `query optimization` |
| Triggers that overlap with another standard | Two standards load when one would suffice | Pick the more specific standard, narrow the broader one |
| Triggers that mirror the filename | Only matches if the user names the file | Add domain language users actually type |
| More than 25 triggers per standard | Suggests the standard covers too many concerns | Split into focused standards |

## Splitting and Merging

**Split a standard when:**

- It exceeds 500 lines and covers multiple distinct concerns
- Its triggers must be split into two non-overlapping sets to be precise
- Two unrelated subsystems would benefit independently

**Merge standards when:**

- Two standards share more than 50% of their triggers
- The combined content is under 300 lines
- The split forces the model to load both files for every task in the area

**Promote a standard to a rule when:**

- It has been triggered by a majority of tasks for an extended period
- Its guidance is referenced by other rules
- Skipping it caused recurring defects across unrelated domains

**Demote a rule to a standard when:**

- Its content is technology-specific
- It rarely shapes responses in practice
- Its trigger surface naturally narrows

Document every promotion and demotion in `decisions.md` of the relevant spec folder.

## Skills vs Rules vs Standards

A separate dimension: skills are workflows the user invokes, not passive guidance.

| Concept | Where | Loaded when | Purpose |
|---------|-------|------------|---------|
| Rule | `rules/*.md` | Always | Behavior shaping |
| Standard | `standards/*.md` | On trigger match | Domain knowledge |
| Skill | `skills/*/SKILL.md` | User invokes via `/<name>` | Multi-step workflow |
| Agent | `agents/*.md` | Orchestrator delegates | Specialized task execution |
| Hook | `hooks/*.{py,sh}` | Tool invocation | Pre/post tool enforcement |
| Checklist | `checklists/checklist.md` | Verification phases | Review categories |

When designing new guidance, ask: is this content (rule/standard), workflow (skill), delegated work (agent), or runtime enforcement (hook)?

## Maintenance Discipline

- Every new file in `rules/` or `standards/` must be registered in `rules/index.yml`
- Every removed file must be unregistered in the same commit
- Run `python3 scripts/validate-counts.py` and `python3 scripts/validate-cross-refs.py` before committing changes to either tier
- Trigger words are part of the public API of a standard. Treat trigger changes as breaking changes
- Cross-references between standards belong in the body, not in `index.yml` descriptions

## MCP Server Triage

MCP servers consume runtime context and rate budget. Treat them like Tier 1: every active server costs every session. Apply these rules:

| Rule | Rationale |
|------|-----------|
| Maximum 5-6 active MCP servers | Context window pressure, output schema bloat |
| Scope each server to specific skills or agents | Avoid loading data-heavy servers for unrelated work |
| Disable servers that have not been used for an extended period | Dead weight in every session |
| Prefer per-skill MCP scoping over global activation | Smaller token footprint per task |
| Document each MCP server's purpose and trigger set in `mcp-security.md` | Otherwise nobody remembers what it does |

When evaluating a new MCP server: would a periodic CLI fetch satisfy the same need? If yes, prefer the CLI. MCP is for capabilities that need persistent connection, structured tool calls, or cross-session state.

## Quick Reference

When unsure, walk this checklist:

1. Is the content universal? → rules/
2. Is the content domain-specific? → standards/
3. Is the content a workflow? → skills/
4. Is the content delegated work? → agents/
5. Is the content runtime enforcement? → hooks/
6. Is the content a verification list? → checklists/

If two categories fit, choose the one with the smaller default load.

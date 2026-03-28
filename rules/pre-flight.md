# Pre-Flight

## Core Rule

No implementation without pre-flight verification. Wrong-direction work is the most expensive mistake.

## When to Apply

Before implementing any non-trivial change. Skip for single-line fixes, typos, and config tweaks where the change is obvious.

## Gate

Run these checks in order. If any fails, stop and resolve before writing code.

### 1. Duplicate Check

Search the codebase, open PRs, recent branches, and community packages for existing solutions.

| Where to look | How |
|----------------|-----|
| Current codebase | Grep for keywords, function names, feature terms |
| Open PRs | `gh pr list --search "<keywords>"` |
| Recent branches | `git branch -a --list "*<keyword>*"` |
| Closed PRs | `gh pr list --state closed --search "<keywords>"` |
| Community packages | Search for established libraries that solve the problem. Check npm, PyPI, or the relevant registry |

If a solution exists in the codebase, reuse or extend it. If a well-adopted package exists, suggest it before implementing manually. Building from scratch what a maintained library already solves is wasted effort and ongoing maintenance burden.

When suggesting a package, follow the evaluation criteria from `rules/code-style.md` Dependencies section: compare top options, check maintenance activity, community size, vulnerabilities, and bundle size.

### 1b. Market and Competitor Research (Feature Planning)

When planning features, improvement roadmaps, or new modules, research existing solutions exhaustively before designing anything. Every feature must be grounded in patterns validated by the market. Inventing from scratch when proven patterns exist is wasted effort and a source of wrong-direction work.

**When this gate applies:** any new feature, workflow, integration, or UX pattern. Does not apply to bug fixes, config changes, or purely internal refactors.

#### Research scope

Search every category. Do not stop after finding 2-3 results. The goal is to understand how the entire market solves the problem, then extract the best patterns.

| Category | What to search | How | Minimum effort |
|----------|---------------|-----|----------------|
| US enterprise platforms | Category leaders in the domain | Web search: "{domain} software features", "{domain} platform capabilities" | Fetch 3+ product feature pages |
| US/CA startups | Emerging competitors and niche players | GitHub search, web search: "{domain} startup features" | Fetch 3+ product pages |
| European platforms | UK, German, French, Eastern European alternatives | Web search in English: "{domain} software UK", "{domain} platform Europe" | Fetch 2+ product pages |
| Brazilian platforms | Local competitors and market-specific solutions | Web search in Portuguese: "software de {dominio} funcionalidades", "plataforma {dominio} Brasil" | Fetch 2+ product pages |
| Latin American platforms | Mexican, Argentine, Colombian alternatives | Web search in Spanish: "software de {dominio} funcionalidades" | Fetch 1+ product pages |
| Open source (same stack) | Projects using the same language/framework | GitHub search: "{domain}" filtered by language, sorted by stars | Read schema/models of top 3 |
| Open source (any stack) | Best implementations regardless of language | GitHub search: "{domain}" sorted by stars, all languages | Read architecture of top 3 |
| User's own repos | Prior art and reusable patterns across all accounts | Check every GitHub account the user has. Search for relevant repos. Read schemas, services, and data models | Check all accounts, read key files |
| Review/comparison sites | Aggregated feature lists and user feedback | Web search: "best {domain} software comparison", "{domain} software reviews" | Read 1-2 comparison articles |
| API documentation | How market leaders structure their data models | Search for "{platform} API reference", "{platform} developer docs" | Read 2+ API schemas |

#### What to extract from each source

For every platform or project researched, extract and document:

1. **Feature inventory**: what features exist. List each one, not just categories.
2. **Data model**: entities, relationships, and how they connect. If the source is open source, read the actual schema. If commercial, infer from the UI/API.
3. **Integration points**: how modules reference each other. Does creating a quote auto-create a job? Does completing a job auto-generate an invoice? Map every cross-module trigger.
4. **Lifecycle flows**: the full journey from first touch to completion. What are the steps, statuses, and transitions?
5. **UX patterns**: how the user interacts. One-click conversions? Drag-and-drop? Inline editing? Approval workflows?
6. **Differentiators**: what does this platform do that others do not? What is genuinely unique?
7. **Gaps**: what is missing from this platform that others have?

#### How to document findings

Create a structured summary per source. In the spec folder's `references.md`:

```markdown
### Platform Name (Region, Type)

**Features:** bullet list of all features found
**Data model highlights:** key entities and relationships
**Integration patterns:** cross-module triggers and automations
**Unique approach:** what they do differently
**Gaps vs our platform:** what they lack that we have
**Ideas to adopt:** specific patterns worth implementing
```

#### Cross-reference analysis

After researching all sources, build a cross-reference matrix:

| Feature/Pattern | Source A | Source B | Source C | Our platform | Action |
|----------------|---------|---------|---------|-------------|--------|
| Quote-to-job conversion | Yes (1-click) | Yes (manual) | No | Missing | Implement |
| Skill-based dispatch | Yes | Yes | Yes | Missing | Implement |
| Progress invoicing | Yes | No | Yes | Missing | Implement |

Features present in 3+ sources are market-validated patterns. Implement them. Features present in only 1 source are differentiators worth evaluating. Features no source has are innovation opportunities worth discussing.

#### Validation principle

**Copy what works. Improve what is weak. Invent only when the market has no answer.**

- If every competitor implements a feature the same way, do it the same way. Users expect it.
- If competitors implement it poorly (bad UX, missing edge cases), improve the implementation but keep the concept.
- If no competitor has the feature and the user requests it, design it carefully with extra user validation.
- Never assume a feature is unnecessary because competitors lack it. Ask the user.
- Never assume a feature is necessary because competitors have it. Validate against the user's actual workflow.

#### Research depth by task size

| Task scope | Research depth |
|-----------|---------------|
| Single feature (e.g., "add quote PDF export") | Search 5+ competitors for how they handle it. Read 2+ implementations. |
| Module improvement (e.g., "improve dispatch board") | Search 10+ platforms across all regions. Read 3+ open source implementations. Build comparison matrix. |
| Full roadmap or architecture plan | Search 15+ platforms. Read 5+ open source projects. Analyze user's own repos across all accounts. Build comprehensive cross-reference matrix. Document in spec folder. |

#### Time investment

Research is not a shortcut to skip. It is the most valuable time in the planning phase. A 30-minute research session that finds a proven pattern saves days of wrong-direction implementation.

Do not present a plan until research is complete. If the user asks to start implementing before research is done, explain what remains and why it matters.

### 2. Architecture Fit

Read the surrounding code. Confirm the new code fits the existing patterns, except when existing patterns violate `~/.claude/` rules. Rules always take priority.

- What conventions does this area of the codebase follow?
- What abstractions already exist that the new code should use?
- Would this change require modifying callers, consumers, or dependents?
- Does it belong in this module, or does it belong somewhere else?

If the change doesn't fit the existing architecture, raise it before implementing.

### 3. Interface Verification

Verify every external interface the implementation will touch.

| Interface | How to verify |
|-----------|---------------|
| Functions to call | Read their signatures and return types |
| APIs to consume | Read the route, controller, or schema |
| Libraries to use | Fetch docs (llms.txt or official docs) |
| Database tables | Read the schema or migration files |
| Config and env vars | Read `.env.example` or consuming code |

No guessing. If the interface is ambiguous, clarify before coding.

### 4. Root Cause Confirmation (Bug Fixes Only)

For bug fixes, confirm the root cause before writing the fix.

- Can you reproduce the bug reliably?
- Can you explain WHY it happens, not just WHERE?
- Can you predict what a specific test input will do?

If any answer is no, investigate further. Do not write a speculative fix.

### 5. Warning Baseline

Apply the "Warning baseline" section of `checklists/checklist.md` category 17. Run linter, type checker, and test suite on the files you plan to change. Record the current warning count. After implementation, the count must be equal to or lower.

### 6. Scope Agreement

Confirm the scope is bounded and agreed upon.

- What files will change? List them.
- What will NOT change? State the boundary explicitly.
- Are there follow-up tasks that should be separate?

If scope is unclear, ask one question before starting.

## Confidence Signal

After completing the gate, briefly state:

- What was checked and confirmed
- Which interfaces were verified
- What the implementation approach will be

Then proceed. One sentence is enough for small tasks.

## Common Failures

- Starting implementation before reading the existing code in the area
- Assuming a library API works a certain way without checking docs
- Fixing a bug based on a theory that was never tested
- Implementing a feature that already exists in a different module
- Expanding scope mid-implementation without checking with the user

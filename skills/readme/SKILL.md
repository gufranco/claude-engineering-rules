---
name: readme
description: Generate a README and GitHub repo description by analyzing the project's actual codebase, infrastructure, and architecture. Two variants. Marketing (default) for open source and portfolio: hero, badges, highlights grid. Assessment via `--variant assessment` for take-home submissions and architecture audits: technical tone, tables, narrative design decisions. Use when user says "write a README", "generate README", "update README", "repo description", "assessment README", or wants a polished project README. Do NOT use for general documentation updates.
sensitive: true
---
Generate a README and GitHub repository description grounded in the actual codebase. Two variants are supported: marketing (default) and assessment (`--variant assessment`). The marketing variant feels like a product landing page: eye-catching hero section, visual feature grids, architecture diagrams, concrete metrics, quick start that's impossible to miss. The assessment variant feels like an engineering memo: tables for every section, design decisions written as narrative paragraphs, no marketing language. Every claim in both variants must be grounded in the actual codebase. Never invent features.

## When to use

- When starting a new project that needs a professional README.
- When a project has outgrown its initial README and needs a rewrite.
- When preparing a project for public release or portfolio showcase.
- When the README is stale and no longer reflects the codebase.
- When you want the project to stand out on GitHub.

## When NOT to use

- For minor README tweaks like fixing a typo or adding one section.
- When the project has no code yet, just a plan.

## Arguments

This skill accepts optional arguments after `/readme`:

- No arguments: generate a full README and repo description by scanning the entire project. Uses the marketing-grade structure documented in this file.
- `--variant <name>`: pick the README structure variant. Default `marketing`. Currently supported variants:

  | Variant | When to use | Template source |
  |---------|-------------|-----------------|
  | `marketing` | Public release, portfolio, open source. Hero, highlights grid, badges, eye-catching visuals. Default | The structure documented inline in this file |
  | `assessment` | Take-home assessments, interview submissions, pre-submission audits, architecture reviews. Technical and explanatory tone. Tables and concrete examples. Design decisions as narrative paragraphs | `template-assessment.md` in this directory. Also invoked by `/assessment` step 12 |

- `--about-only`: generate only the GitHub repo description and topics, skip README.
- `--section <name>`: regenerate a specific section (e.g., `--section quick-start`).
- `--diff`: update the existing README based on what changed since it was last written.

When `--variant assessment` is passed, read `template-assessment.md` for the full structure and rules. The Deep Scan in Phase 1 still runs because the assessment variant also benefits from grounded data, but the structure, tone, and section list come from the assessment template instead of the marketing structure below.

## Steps

### Phase 1: Deep Scan

Read the project thoroughly. Run these **in parallel**:

1. **Project identity**: read `package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`, `Makefile`, or equivalent to get the project name, version, description, dependencies, and scripts.
2. **Infrastructure and config**: read Terraform files, Docker files, CI/CD configs, `docker-compose.yml`, and deployment configs to understand the infrastructure.
3. **Source code structure**: map the directory tree (`ls -R` or glob) to understand the project layout, modules, and organization.
4. **Existing README**: read the current `README.md` if it exists, to understand what the user already had and what to improve.
5. **Environment and setup**: read `.env.example`, setup scripts, and Makefile targets to document prerequisites and setup steps.
6. **Git context**: run `git remote -v` and `git log --oneline -10` to get the repo URL, recent activity, and contributor count.
7. **Visual assets**: check for logo files (`logo.png`, `logo.svg`, `banner.png`, `.github/assets/`, `docs/images/`) and existing screenshots or demos.
8. **License and metadata**: read `LICENSE`, `.github/FUNDING.yml`, badges in existing README.

### Phase 2: Architecture and Identity Analysis

From the scan results, build a project profile:

- **Type**: library, CLI tool, web app, API service, infrastructure, monorepo, dotfiles, or combination.
- **Stack**: languages, frameworks, databases, cloud services, CI/CD tools.
- **Scale signals**: multi-region, microservices, event-driven, serverless, multi-tenant, monorepo with N packages, etc.
- **Differentiators**: what makes this project stand out? Look for unique combinations, unusual scale, well-solved hard problems, or opinionated design choices.
- **Personality**: infer the project's tone from existing docs, comments, and commit messages. Technical and serious? Fun and playful? Opinionated and sharp? Match it.
- **Metrics inventory**: count concrete numbers: modules, services, endpoints, tests, config files, CLI commands, supported platforms, dependencies, lines of code by language. These become the quantified summary.

### Phase 3: Generate README

Write the README following the structure and visual guide below. Every section must be grounded in what was found in Phase 1. If a section doesn't apply, skip it. The goal is a README that makes someone stop scrolling and star the repo.

### Phase 4: Generate GitHub About

Generate a concise repo description (max 350 characters) and a list of topic tags. See the "GitHub About" section below.

### Phase 5: Present and Apply

1. Show the full README to the user for review.
2. Show the GitHub About description and topics.
3. Ask if they want changes before writing.
4. **Resolve account** per `standards/borrow-restore.md` before applying GitHub About. Match the remote URL against authenticated accounts, switch if needed.
5. After approval:
   - Write the README.md file.
   - Apply the GitHub About using `gh repo edit --description "<desc>"` and `gh repo edit --add-topic <topic>` commands.
   - Restore the original account per `standards/borrow-restore.md`.

## README Structure

Use this structure as a guide. Skip sections that don't apply. Reorder if it makes more sense for the project.

### 1. Hero Section

The first thing anyone sees. It must create instant visual identity and communicate what the project does in under 5 seconds. The 5-second test is the explicit acceptance criterion: a developer scrolling fast should know what the project is, that it works, and how to try it without reading a single paragraph.

**Light and dark mode logo via `<picture>`.** This is the canonical pattern as of late 2023. The older `#gh-dark-mode-only` fragment hack is deprecated. Drizzle, tRPC, Vite, Supabase, and Next.js all use this form.

```html
<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="path/to/logo-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="path/to/logo-light.svg">
  <img alt="Project Name" src="path/to/logo-light.svg" width="200">
</picture>

<br>
<br>

<!-- Tagline: one line, confident, specific -->
<strong>What it does, concretely, in one sentence.</strong>

<br>
<br>

<!-- Badge bar: see "Badges" section below for the cap and allowlist -->
[![CI](badge-url)](link)
[![Version](badge-url)](link)
[![License](badge-url)](link)

</div>

<p align="center">
  <a href="#documentation">Docs</a> &nbsp;|&nbsp;
  <a href="https://discord.gg/..."><strong>Discord</strong></a> &nbsp;|&nbsp;
  <a href="https://twitter.com/..."><strong>Twitter</strong></a> &nbsp;|&nbsp;
  <a href="#contributing">Contributing</a> &nbsp;|&nbsp;
  <a href="https://github.com/.../issues">Issues</a>
</p>
```

The **navigation pill row** under the badges is the pattern Bun, Zod, and Astro use. Zero scroll cost, gives the reader an escape hatch to the deeper docs and the community channels. Skip channels that do not exist for the project.

When the project has only one logo, use a single `<img>` and skip the `<picture>` wrapper. Never use a placeholder. If no logo exists, omit the image entirely and lead with the bold tagline.

After the centered hero, add a **metrics bar**: a single line or short paragraph with concrete numbers that make the scope tangible. Use bold for the numbers.

Example:
```markdown
**12** modules · **30+** AWS services · **6** regions · **200+** tests · deploys in **~30 min**
```

For CLI tools or libraries, quantify differently:
```markdown
**45** commands · **3** platforms · **zero** dependencies · **<5ms** startup
```

**Demo immediately.** The hero stack ends with one of three demo elements: an animated GIF for visual tools, an asciinema cast for CLI tools, or a 5-line code snippet for libraries. Place this within the first scroll. The "demo first" pattern is now baseline. Hyperfine opens with a GIF. Hono opens with a 4-line code example. Zod opens with a `z.object` schema definition.

### 2. Highlights Grid

A visual feature showcase that reads like a product landing page. Use an HTML table to create a 2-column or 3-column grid. Each cell has a short title and a one-line description.

```html
<table>
<tr>
<td width="50%" valign="top">

### Title A
One-line description of what this feature does and why it matters.

</td>
<td width="50%" valign="top">

### Title B
One-line description of what this feature does and why it matters.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Title C
One-line description of what this feature does and why it matters.

</td>
<td width="50%" valign="top">

### Title D
One-line description of what this feature does and why it matters.

</td>
</tr>
</table>
```

**Rules for the grid:**
- 4 to 8 cells. Pick the most impressive or differentiating features.
- Each title is 2-4 words. No fluff.
- Each description is one sentence. Specific, not generic. "Deploys to 6 AWS regions with one command" not "Easy deployment".
- Order by impact: most impressive first.

### 3. The Problem and The Solution

Two short sections that frame the project as a story. Why does this exist? What pain does it kill?

**The Problem**: 2-3 sentences max. Describe the pain point that motivated the project. Be specific and relatable. Include a third-party endorsement quote when one exists; pnpm leads with a Microsoft Rush team quote about disk efficiency, which is the single strongest social-proof move available.

**The Solution**: how does this project solve it? If alternatives exist, include a comparison table. Be fair to alternatives but highlight genuine advantages. The search query "Project X vs Y" is high-intent; the comparison table captures that traffic. Use plain `Yes` and `No` text instead of emoji to keep the table accessible to screen readers and consistent in fixed-width contexts:

```markdown
| Capability | This Project | Alternative A | Alternative B |
|:-----------|:------------:|:-------------:|:-------------:|
| Feature 1  | Yes          | Yes           | No            |
| Feature 2  | Yes          | No            | Yes           |
| Feature 3  | Yes          | No            | No            |
```

For richer tables, replace `Yes` with a short capability descriptor like "Built-in" or "Plugin" or "Partial" so the cell content tells the reader more than a binary. Never rely on color alone to communicate; screen readers ignore color, and red/green is invisible to about 8% of male readers.

### 4. Architecture

Mermaid diagrams for projects with enough complexity to warrant them. Use the diagram type that best fits:

- **Flowchart** (`graph LR` or `graph TD`): system architecture, data flow between components.
- **Sequence diagram**: request/response flows, multi-service interactions.
- **C4 Context**: high-level system boundaries for larger projects.

```markdown
```mermaid
graph LR
    A[Client] --> B[API Gateway]
    B --> C[Service A]
    B --> D[Service B]
    C --> E[(Database)]
    D --> F[(Cache)]
`` `
```

**Diagram rules:**
- Max 15-20 nodes per diagram. Split into multiple if needed.
- Use descriptive labels, not single letters.
- Include the data flow direction.
- For multi-layer architectures, use `subgraph` to group related components.
- Skip this section entirely for simple projects (CLIs, small libraries).

### 5. What's Included

Categorized feature list. Group by domain, not by file. Use tables with two columns: feature and description.

```markdown
### Category Name

| Feature | Description |
|:--------|:------------|
| Feature A | What it does, concretely |
| Feature B | What it does, concretely |
```

Categories come from the project's actual domains: Infrastructure, Security, Data Layer, Monitoring, CLI Commands, Components, etc.

### 6. Demo / Screenshots

If the project has visual output (web app, CLI with TUI, desktop app), this section is mandatory. If no screenshots or demos exist yet, add the section with a placeholder structure and a comment telling the user to add them.

**For CLI tools**, show terminal output in a code block or reference an asciinema recording:

```markdown
[![asciicast](https://asciinema.org/a/XXXXX.svg)](https://asciinema.org/a/XXXXX)
```

**For web apps**, use a screenshot with a subtle border:

```html
<div align="center">
<img src="docs/images/screenshot.png" alt="App screenshot" width="700">
</div>
```

**For GitHub light/dark mode support** (when the project has both variants):

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/screenshot-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/images/screenshot-light.png">
  <img alt="App screenshot" src="docs/images/screenshot-light.png" width="700">
</picture>
```

### 7. Quick Start

The most important section after the hero. It must be prominent, copy-pasteable, and verifiable. A reader should go from zero to running in under 60 seconds.

```markdown
## Quick Start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Node.js | >= 20 | [nodejs.org](https://nodejs.org) |
| Docker | >= 24 | [docker.com](https://docker.com) |

### Setup

```bash
git clone https://github.com/user/repo.git
cd repo
npm install
cp .env.example .env
npm run dev
```

### Verify

```bash
curl http://localhost:3000/health
# {"status":"ok"}
```
```

**Rules:**
- Prerequisites in a table, not a bullet list.
- Setup commands numbered only if order matters, otherwise a single code block.
- Always end with a verification step that proves it works.
- Include the expected output of the verification command.

### 7b. For Contributors and Reviewers

This subsection lowers the cost of contribution and pre-empts PR review back-and-forth. Include it when the project expects external contributors or when the project has more than one regular contributor.

The generated section has four parts.

**Reproducing a bug.** Concrete steps from clone to running a minimal reproducer. Reuse the same commands as the Quick Start verification step, plus any seed scripts or fixture files needed. A reviewer who cannot reproduce a reported bug pushes back harder.

```markdown
### Reproducing a bug

```bash
git clone https://github.com/user/repo.git
cd repo
npm install
cp .env.example .env
npm run db:seed
npm run dev
```

To reproduce reported bugs, follow the steps above and then read the bug report's "Steps to reproduce" section.
```

**Project conventions.** A table listing concrete conventions detected from the codebase. Surfacing these in the README pre-empts review comments that would otherwise litigate style.

```markdown
### Project conventions

| Convention | Source |
|------------|--------|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Branch naming | `feature/`, `bugfix/`, `hotfix/`, `chore/` prefixes |
| Lint configuration | [.eslintrc.json](.eslintrc.json) |
| Code style | [Prettier](https://prettier.io/) with [prettier.config.mjs](prettier.config.mjs) |
| Review process | One human reviewer + CodeRabbit. Expect first response within 1 business day |
```

**Non-obvious decisions.** A short list of 3 to 5 architectural choices the project made deliberately, with one-line rationale each. These are the choices that reviewers would otherwise spend a thread asking about. This subsection cannot be auto-generated reliably; `/readme` prompts the user with: "Name 3 to 5 architectural choices that newcomers ask about. One sentence each."

```markdown
### Non-obvious decisions

- Single-writer Postgres without sharding. The data fits and the operational cost of sharding outweighs the latency benefit at this scale.
- Synchronous email sending in the request path. The volume is low enough that the queue overhead would dominate.
- Branded `UserId` and `OrderId` types. Mixed-up IDs were the source of two production bugs last year.
```

**Issue tracker.** Link to where bugs and feature requests get filed. Deferred items from PR reviews land here.

```markdown
### Issue tracker

Bugs and feature requests live in [GitHub Issues](https://github.com/user/repo/issues). Please file before opening a PR.
```

#### How /readme produces this subsection

Phase 1 Deep Scan gains these scans:

1. **Detect commit format.** Read recent commits via `git log --oneline -20`. Match against Conventional Commits patterns or any other recognizable format. Record the result for the Project conventions table.
2. **Detect lint and style configs.** Look for `.eslintrc.*`, `prettier.config.*`, `.editorconfig`, `pyproject.toml [tool.ruff]`, `clippy.toml`, `golangci.yml`. Cite the discovered files in the table.
3. **Detect AI review bots.** Look for `.coderabbit.yml`, `.coderabbit.yaml`, `.greptile.yml`, `.cursorrules`, `.cursor/`, `.sourcery.yaml`, `korbit.yml`. List the discovered bots in the conventions table.
4. **Detect issue tracker.** Read repo metadata via `gh repo view --json hasIssuesEnabled,url`. If issues are disabled, look for `ISSUE_TEMPLATE/` or `BUG_REPORT.md` template files. If neither, omit the section and leave a comment recommending the user add one.
5. **Detect testing instructions.** Look for `make test`, `npm run test`, `pytest`, `go test ./...`, or equivalent. The reproducing-a-bug instructions reuse the same command.

#### Skip conditions

If the project is a small CLI tool or a personal dotfiles repo with no expected reviewers, skip the entire "For Contributors and Reviewers" subsection. The signal for skipping: no recent PRs in the repo, or no recent contributors other than the author.

### 7c. GitHub Alerts for Critical Callouts

GitHub-flavored Markdown supports five alert types as of late 2023. Use them sparingly for content that genuinely deserves a visual break. Overuse turns the README into a wall of colored boxes and dilutes their effect.

```markdown
> [!NOTE]
> Useful information that users should know, even when skimming content.

> [!TIP]
> Helpful advice for doing things better or more easily.

> [!IMPORTANT]
> Key information users need to know to achieve their goal.

> [!WARNING]
> Urgent info that needs immediate user attention to avoid problems.

> [!CAUTION]
> Advises about risks or negative outcomes of certain actions.
```

When to use each:

| Alert | Use for |
|-------|---------|
| `NOTE` | Behavior the reader might miss, like a default value or a non-obvious fallback |
| `TIP` | An optimization or shortcut that improves the experience but is not required |
| `IMPORTANT` | A required step or constraint that the reader must internalize, like a peer dependency or minimum runtime version |
| `WARNING` | A footgun or breaking-change announcement that risks production impact |
| `CAUTION` | A destructive operation like database drops, force-pushes, or irreversible config changes |

Two alerts in the entire README is healthy. Five is too many. Reserve them for callouts that would otherwise hide inside a paragraph.

### 7d. Sponsors and Backers

Sustainable open source funding is now expected for projects that ask for serious adoption. The pattern from pnpm, Biome, tRPC, and TanStack Query is a tiered sponsor section with logos rendered at size proportional to the contribution tier.

```markdown
## Sponsors

### Platinum

<a href="https://example.com"><img src="logos/sponsor-platinum.svg" alt="Sponsor Name" width="200"></a>

### Gold

<a href="https://example.com"><img src="logos/sponsor-gold.svg" alt="Sponsor Name" width="140"></a>

### Silver

<a href="https://example.com"><img src="logos/sponsor-silver.svg" alt="Sponsor Name" width="100"></a>

### Backers

<a href="https://opencollective.com/your-project"><img src="https://opencollective.com/your-project/backers.svg?width=890" alt="Backers"></a>
```

When to include the section:

- The project has a `FUNDING.yml` file in `.github/`.
- The project is on Open Collective, GitHub Sponsors, or Polar.
- The project has at least one existing sponsor or is actively soliciting one.

When to skip:

- Personal projects, dotfiles, internal-only repos.
- New projects with no sponsors and no immediate plans to ask.

Render sponsor logos from a controlled directory like `assets/sponsors/` so the file paths stay stable. Update the section in the same PR that adds the sponsor.

### 7e. AI Companion Files

Modern READMEs ship with companion files that help AI agents and assistants navigate the repo. Two conventions are emerging.

**`llms.txt` at the site root** for documentation sites. Plain-text Markdown file that summarizes the project for LLM consumption. Required structure: H1 with project name, blockquote summary, optional paragraphs, then H2 sections containing markdown links of the form `[name](url): optional notes`. Original spec at `llmstxt.org`. Adoption is around 10% of sites overall, near-100% among developer-facing SaaS. Cursor, Windsurf, Claude Code, and similar IDE agents fetch `/llms.txt` and `/llms-full.txt` when pointed at a documentation domain.

```markdown
# Project Name

> One-paragraph summary of what the project does and who it is for.

## Docs

- [Quick Start](https://example.com/docs/quick-start): get running in 60 seconds
- [API Reference](https://example.com/docs/api): full type signatures and examples

## Examples

- [Basic Example](https://example.com/examples/basic): the 5-line demo
- [Advanced Example](https://example.com/examples/advanced): full-stack walkthrough
```

Generate `llms.txt` when the project has a documentation site distinct from the GitHub README. Skip when the README is the only documentation.

**`AGENTS.md` at the repo root** for in-repo AI agent context. Emerged mid-2025 from a Sourcegraph, OpenAI, Google, and Cursor collaboration, now maintained by the Agentic AI Foundation under the Linux Foundation. Single Markdown file that AI coding agents read for project context: dev commands, conventions, deploy notes, code map. Distinct from `llms.txt`, which is a web standard, and distinct from per-tool files like `CLAUDE.md` or `.cursor/rules`.

Generate `AGENTS.md` when the project will be touched by AI coding agents. Include: project overview, common commands, test conventions, where to find what, and any non-obvious constraints. Match the tone of a senior engineer briefing a new hire on day one.

### 7f. Multilingual Variants

For projects with an international audience, ship one README file per locale and a language switcher at the top of each.

**Filename convention** uses ISO 639-1 or BCP 47 suffixes. English stays as `README.md`. Other locales get `README.<locale>.md`.

| Locale | Filename |
|--------|----------|
| Brazilian Portuguese | `README.pt-BR.md` |
| Simplified Chinese | `README.zh-CN.md` |
| Traditional Chinese | `README.zh-TW.md` |
| Japanese | `README.ja.md` |
| German | `README.de.md` |
| Spanish | `README.es.md` |
| French | `README.fr.md` |

**Language switcher at the top, before any content.** Format as a single line of pipe-separated links so the reader can jump without scrolling:

```markdown
**Read this in other languages:** [English](README.md) | [日本語](README.ja.md) | [Português](README.pt-BR.md) | [中文](README.zh-CN.md) | [Deutsch](README.de.md)
```

GitHub does not negotiate `Accept-Language`. Users always click the switcher. For projects with many translations like Supabase's 40-plus locales, a translation grid pattern, one column for flag icons and one for language names, scales further than the inline pipe list.

When to localize:

- The project has demonstrated international adoption signals: issues in non-English languages, contributors from multiple regions.
- A core maintainer or volunteer commits to keeping the translation current.

When to skip:

- New projects without international traction.
- Solo projects where the maintainer cannot keep translations synchronized with the English version.

### 8. Project Structure

Directory tree with one-line descriptions. For large projects, wrap in a collapsible section.

```html
<details>
<summary><strong>Project structure</strong></summary>

`` `
src/
  api/          # REST endpoints and middleware
  services/     # Business logic
  models/       # Database models and schemas
  utils/        # Shared utilities
tests/          # Test suites
infra/          # Terraform modules
`` `

</details>
```

For smaller projects (< 10 directories), show the tree directly without collapsing.

### 9. Development Commands

Tables grouped by category. Only include if the project has a Makefile, scripts, or task runner.

```markdown
### Development

| Command | Description |
|:--------|:------------|
| `npm run dev` | Start development server with hot reload |
| `npm run test` | Run test suite with coverage |
| `npm run lint` | Lint and format check |

### Infrastructure

| Command | Description |
|:--------|:------------|
| `make deploy` | Deploy to staging |
| `make tf-plan` | Preview infrastructure changes |
```

### 10. Configuration / Environment Variables

Tables with variable name, description, required/optional, and default value.

```markdown
| Variable | Description | Required | Default |
|:---------|:------------|:--------:|:--------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |, |
| `PORT` | Server port | No | `3000` |
| `LOG_LEVEL` | Logging verbosity | No | `info` |
```

### 11. API Reference

For projects with APIs, include endpoint tables. For large APIs, link to external docs and show only the most important endpoints.

```markdown
| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `GET` | `/api/users` | List all users (paginated) |
| `POST` | `/api/users` | Create a new user |
| `GET` | `/api/users/:id` | Get user by ID |
```

### 12. FAQ

4-6 questions a newcomer would ask. Use collapsible sections to keep the page clean.

```html
<details>
<summary><strong>How do I configure X?</strong></summary>
<br>

Direct, useful answer with a code example if applicable.

</details>

<details>
<summary><strong>Why did you choose Y over Z?</strong></summary>
<br>

Honest, technical answer explaining the trade-off.

</details>
```

### 13. License

Short and simple. One line with the license name and a link to the full text.

```markdown
## License

[MIT](LICENSE)
```

## Style Guide

### Voice and Tone

- **Confident and direct.** No hedging ("might", "should", "could potentially"). State what the project does.
- **Technical but magnetic.** Assume the reader is a developer. Respect their intelligence but make them excited.
- **Show, don't tell.** Instead of "easy to set up", show a 3-line setup. Instead of "fast", show a benchmark. Instead of "flexible", show 3 different config examples.
- **Opinionated is good.** If the project made deliberate choices, state them proudly. "We use X because Y" is more compelling than "supports X and Y".

### Visual Hierarchy

The README should be scannable in 10 seconds. A developer scrolling fast should understand what the project does without reading a single paragraph.

1. **Hero with logo/tagline** catches the eye.
2. **Metrics bar** establishes credibility and scale.
3. **Highlights grid** communicates top features visually.
4. **Architecture diagram** shows the system at a glance.
5. **Quick Start** lets them try it immediately.
6. **Everything else** is reference material below the fold.

### Formatting Rules

- **Centered hero section** using `<div align="center">`. This is the only centered section.
- **HTML tables for feature grids** when you need multi-column layouts that Markdown tables can't achieve.
- **Markdown tables for data** (commands, env vars, endpoints, prerequisites).
- **Mermaid diagrams** for architecture. Keep them readable, max 20 nodes.
- **Collapsible sections** (`<details>`) for verbose content: project structure, FAQ, extended config.
- **Code blocks** for every command. Always include the language identifier.
- **Horizontal rules** (`---`) to separate the hero from the content. Use sparingly elsewhere.
- **Bold numbers** in the metrics bar to make them pop.
- **Consistent alignment**: use `:--------` for left-align, `:--------:` for center-align in tables. Align columns purposefully: names left, statuses center, descriptions left.

### Badges

Only for verifiable, meaningful facts. Grouped and ordered consistently. Cap at 5 to 8 badges in the hero. More than 8 dilutes signal and pushes content below the fold.

**Order**: build status, version and release, downloads, license, then optional extras like coverage, bundle size, and community.

**High-signal allowlist.** Each badge in this list earns its slot because it answers a real trust question.

| Badge | What it tells the reader | Source |
|-------|--------------------------|--------|
| CI status | "Does it build?" | GitHub Actions, CircleCI |
| Package version | "What version is current?" | npm, PyPI, crates.io, JSR |
| Downloads per month or week | "Is anyone using it?" | npm, PyPI, GitHub Releases |
| License | "Can I use it?" | shields.io static badge |
| Coverage | "Are the tests honest?" | Codecov, Coveralls |
| Bundle size | "Will it bloat my app?" | Bundlephobia, size-limit |
| Community count | "Is there help when I get stuck?" | Discord, Slack |
| OpenSSF Scorecard | "Is the supply chain audited?" | scorecard.dev |
| Star History snapshot | "Is momentum building?" | Use only after the project crosses ~1k stars |

**OpenSSF Scorecard badge format** for security-sensitive projects:

```markdown
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/{owner}/{repo}/badge)](https://scorecard.dev/viewer/?uri=github.com/{owner}/{repo})
```

The badge requires the `scorecard-action:v2` GitHub Action with `publish_results: true` and `id-token: write` permission.

**Denylist.** These add noise without trust signal and should never appear:

- "Made with love", "Built with passion", "FORTHEBADGE" decorative tags
- "Awesome" badges that link to nothing or to a placeholder list
- Generic technology stack badges for the project's primary language. The language is already visible in the GitHub repo header
- Badges for tools that are not central to the project's value proposition
- Broken or outdated badges that show error states or that point at deleted services

**Style consistency.** Pick one shields.io style and keep it across every badge. Common choices: `flat`, `flat-square`, `for-the-badge`. Mixing styles looks unfinished.

**Color semantics.** Green for healthy or positive, red for failing or critical, blue for informational. Shields.io defaults map status colors automatically.

**Alt text on every badge.** The `[![alt](url)](link)` markdown form includes alt text inside the brackets by default. Custom HTML `<img>` badges need explicit `alt=""`. Screen readers stay silent on image-only badges.

### Quantification

Make the project's scope tangible with specific numbers. These are the most persuasive thing in a README because they can't be faked.

- Number of modules, services, components, or packages.
- Number of cloud services, regions, or resources managed.
- Lines of Terraform, tests, or endpoints.
- Concrete metrics: "deploys in ~30 min", "0.5-128 ACU scaling range", "6 regions".
- Performance: "cold start < 100ms", "handles 10k req/s", "< 5MB binary".
- Reliability: "99.9% uptime SLO", "zero-downtime deploys", "100% test coverage".

**Never estimate. Count from the source.**

### What NOT to Include

- **No "Contributing" section** unless the user asks for it.
- **No "Acknowledgments" section** unless the user asks for it.
- **No version history or changelog** in the README. Link to releases instead.
- **No "Built with" section** that just lists logos. The badges and stack description cover this.
- **No placeholder text.** If information is unknown, skip the section entirely.
- **No AI attribution.** Never add "Generated by AI" or similar markers.
- **No marketing fluff words.** "Revolutionary", "game-changing", "next-generation", "cutting-edge", "blazing fast" are all banned. Let the numbers and features speak.

## GitHub About

The About description renders as the meta-description in Google SERP snippets. Topics drive GitHub search relevance and Topic-page rankings. The social preview image is what every Twitter, Slack, Discord, and LinkedIn unfurl will show. These three fields are the single highest-leverage SEO surface in a GitHub repo.

### Description

- Max 350 characters.
- Format: `[What it is] + [key differentiator] + [quantified scope]`.
- Front-load the most-searched keyword. The first 70 characters get the heaviest SEO weight and appear unwrapped in most listing UIs.
- No emojis. No trailing period.
- Example: `Production-grade multi-region AWS infrastructure as code. 9 Terraform modules, 30+ AWS services, 6 regions, one terraform apply`

### Topics

GitHub enforces a hard limit of **20 topics per repo**, each up to **50 characters**, lowercase letters, numbers, and hyphens only. Underscores are not permitted. Use all 20 slots.

- **Use all 20 slots.** Mix broad terms (`javascript`, `web-development`) with narrow ones (`react-component`, `ui-library`). Topics function as LSI keywords and tie the repo to GitHub's related-concepts graph.
- **Drop terms already in the About or repo name.** GitHub already gives those high weight; topics that duplicate them waste slots.
- **Skip the primary language.** GitHub auto-detects and surfaces it separately.
- **Lowercase and hyphens only.** `multi-region`, not `MultiRegion` or `multi_region`. Hyphens are the GitHub convention; underscores are rejected.
- **No generic tags.** `code`, `project`, `awesome`, `app`. These hurt rather than help because they match millions of unrelated repos.
- **Order by specificity, most distinctive first.** GitHub may truncate the list in some UIs; the leading topics get the most visibility.

Apply via `gh repo edit --add-topic <topic>` per the account-safety pattern with `GH_TOKEN=$(gh auth token --user <account>)` prefix.

### Social Preview Image

The image GitHub shows on Twitter, Slack, Discord, LinkedIn, and any other platform that unfurls the repo URL. A repo without a social preview falls back to a generic GitHub-grid screenshot, which is the unmistakable signal of an unfinished project.

- **GitHub minimum**: 640x320 pixels. **Recommended**: 1280x640 pixels.
- **File**: PNG, JPG, or GIF. Under 1 MB.
- **Universal cross-platform sweet spot**: 1200x630 pixels with text inside the center 80% safe zone. This shape works on Twitter, Facebook, LinkedIn, Discord, and Slack without cropping.
- **Solid background**, not transparent. Transparent renders unpredictably on dark-mode platforms.
- **High contrast** between text and background. 4.5:1 minimum for normal text, 3:1 for large text.
- **Include the project name and one-line value prop**. The image is often viewed without the surrounding text, so it has to stand alone.
- **Apply via the repo settings UI**, since the API does not currently expose social preview upload.

## File References (MANDATORY)

Every file mentioned in the README must be a clickable Markdown link to the actual file in the repository. No exceptions.

**Rule:** whenever a file name, path, or directory appears in the README, wrap it as `[file.ext](relative/path/to/file.ext)`. This applies to prose, tables, lists, FAQ answers, collapsible sections, and footnotes. The only places file names may appear unlinked are inside fenced code blocks (where Markdown links do not render) and in inline code spans that represent literal command output.

**How to apply:**

- Resolve the path relative to the README location. For a root-level README, paths are relative to repo root: `[package.json](package.json)`, `[src/api/users.ts](src/api/users.ts)`.
- Directories link to the directory itself: `[src/services/](src/services/)`. GitHub renders directory links as folder views.
- Verify every linked path exists before writing. A broken link is a defect, same severity as inventing a feature.
- When the same file is mentioned multiple times in the same section, link only the first occurrence to avoid visual noise. Subsequent mentions can use plain code spans.
- Inside Markdown tables, keep links intact: `\| [tsconfig.json](tsconfig.json) \| TypeScript compiler config \|`.
- Inside the project structure tree (fenced code block), file names stay unlinked because Markdown links do not render inside code fences. Compensate by adding a linked summary line above or below the tree.

**Examples:**

```markdown
Configuration lives in [.env.example](.env.example) and is validated at startup by [src/config/schema.ts](src/config/schema.ts).

| File | Purpose |
|:-----|:--------|
| [Makefile](Makefile) | Task runner targets |
| [docker-compose.yml](docker-compose.yml) | Local dev stack |
```

This rule is enforced during the self-check at the end of Phase 3. Re-scan the draft and confirm every file name carries a link before presenting to the user.

## Accessibility

READMEs render in browsers, screen readers, and increasingly in AI assistants reading the repo. The legal risk has risen since the European Accessibility Act took effect 2025-06-28. WebAIM's 2024 Million study found color contrast violations on 83.6% of sites surveyed.

- **Every image has alt text.** Including badges. The bracket `![alt](url)` form puts the alt text inside the brackets by default. For decorative-only images, use empty alt `alt=""` so screen readers skip them. Otherwise, screen readers cut off around 125 characters of alt text.
- **Color contrast at 4.5:1 for normal text and 3:1 for large text.** Applies to any custom HTML in the README, especially the centered hero `<div>` with a background color.
- **Never rely on color alone.** Screen readers ignore color. Comparison tables that use only red and green cells without `Yes` and `No` text fail. Pair every color signal with a text or icon label.
- **Heading order matters.** One H1, then H2 for top-level sections, then H3. Screen reader users navigate by heading. Skipping levels breaks the outline. The `<div align="center"><h1>` pattern preserves order while centering.
- **Image-only badges leave screen readers silent.** Shields.io badges include alt text in the markdown form by default. Custom HTML `<img>` badges need explicit `alt=""`.

## Measurement

A README upgrade should show up in measurable repo signals within 30 days. Capture a baseline before the upgrade and compare after.

| Signal | Tool | Notes |
|--------|------|-------|
| Unique visitors and page views | GitHub Insights | 14-day rolling window. Requires push access |
| Clones | GitHub Insights | Leading indicator of intent to use |
| Star trajectory | star-history.com | Embeddable chart, optional in the README itself once the project crosses 1k stars |
| Referral sources | GitHub Insights | Shows what's driving traffic, useful when paired with social posts |
| Long-term history | repohistory.com | Extends GitHub Insights past the 14-day window |
| Daily stars detail | emanuelef/daily-stars-explorer | Deeper star-trajectory analysis |
| Conversion ratios | Manual | Repo views to clones (intent), clones to stars (worth bookmarking), stars to contributors (worth contributing to) |

Capture before the upgrade: baseline star count, weekly view count, clone count. Capture again after 30 days. Significant change correlates with the upgrade if no external mention (HN, Reddit, Twitter) coincided. View counts move first, stars follow.

## Anti-Patterns

| # | Anti-pattern | Why it hurts |
|---|-------------|--------------|
| 1 | Wall of text with no headings | Kills scannability. Use H2 or H3 every screenful |
| 2 | Vanity badges like "MADE WITH LOVE", "FORTHEBADGE", or "Awesome" without an actual Awesome-list link | Aesthetic noise without trust signal. Dilutes the high-signal badges |
| 3 | "TODO: write this section" left in published README | Signals an abandoned or unfinished project |
| 4 | Broken images and dead links | Often after a logo rename. Lint with `markdown-link-check` in CI |
| 5 | 2000-line wall instead of linking out to a docs site | READMEs over 500 lines should split into `/docs` or a dedicated documentation site |
| 6 | Wrong project name in clone command after a repo rename | Breaks the 60-second quick start |
| 7 | Missing LICENSE or contribution guide link | A repo without LICENSE is legally toxic for consumers. Awesome-list inclusion requires one |
| 8 | Outdated screenshots showing prior major versions | Suggests the maintainer no longer touches the README. Auto-generate with Playwright in CI when possible |
| 9 | No demo, no image, no GIF | Pure-text READMEs read as low-effort. The demo-first pattern is now baseline |
| 10 | Overly personal tone like "just something I made real quick lol" | Undercuts the technical content. Match the project's category: technical for libraries, slightly warmer for end-user apps |

## Rules

- **Evidence-based only.** Every feature, service, or capability mentioned must exist in the codebase. Read the actual files.
- **Every file name is a link.** See the "File References" section above. Unlinked file names outside code blocks are a defect.
- **No invented features.** If you didn't find it in the code, don't write about it.
- **Verify commands.** Every setup command in Quick Start must work. Check that referenced scripts and Makefile targets exist.
- **Check paths.** Every file path in the directory tree must exist. Use glob or ls to verify.
- **Quantify accurately.** Count modules, services, and endpoints from the source. Don't estimate.
- **Match project scale.** A small CLI tool gets a focused README with fewer sections. A multi-region infra project gets the full treatment. Never pad a small project with unnecessary sections.
- **Preserve user customizations.** If the user already has sections they wrote (like a specific "About" or custom badges), keep them unless asked to replace.
- **Visual assets must exist.** Never reference an image, logo, or screenshot that doesn't exist in the repo. If no visual assets exist, skip those elements and note it as a follow-up.
- **Test the visual output.** After generating, mentally render the Markdown. Check that HTML tables, Mermaid diagrams, and collapsible sections are properly closed and will render on GitHub.
- **5-second test.** A developer scrolling fast should know what the project does, that it works, and how to try it within 5 seconds of landing. If the hero stack does not pass this test, restructure.
- **Cap the hero at 5-8 badges.** More than 8 dilutes signal. Pull the rest into a "Status" section below the fold if they earn the slot.
- **Demo-first.** A GIF, asciinema cast, or 5-line code snippet within the first scroll. No exceptions.

## Related skills

- `/ship commit` - Commit the README changes.
- `/ship pr` - Create a PR with the README update.
- `/assessment` - Audit the implementation for completeness before documenting it.

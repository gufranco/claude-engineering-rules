# Skill Authoring

## Required Frontmatter

Every skill file must have YAML frontmatter with at minimum `name` and `description`.

```yaml
---
name: deploy-preview
description: Deploy a preview environment for the current branch
allowed-tools:
  - Bash
  - Read
  - Glob
---
```

## Frontmatter Fields

| Field | Required | Purpose |
|-------|----------|---------|
| `name` | Yes | Unique identifier, used to invoke the skill |
| `description` | Yes | What the skill does, used for matching when the user references it |
| `allowed-tools` | No | Restrict which tools the skill can use. Omit for full access |
| `sensitive` | No | Set to `true` for destructive skills. Requires explicit user confirmation before execution |

## Allowed-Tools Scoping

Scope every skill to the minimum set of tools it needs. A skill that only reads files must not have access to Bash. A skill that only searches must not have access to Write or Edit.

```yaml
# Read-only analysis skill
allowed-tools:
  - Read
  - Glob
  - Grep

# Code modification skill
allowed-tools:
  - Read
  - Edit
  - Glob
  - Grep
  - Bash
```

## Sensitive Flag

Mark skills that perform destructive or irreversible operations.

```yaml
---
name: database-reset
description: Reset the development database to a clean state
sensitive: true
allowed-tools:
  - Bash
  - Read
---
```

## The $ARGUMENTS Variable

User input after the skill name is available as `$ARGUMENTS` in the skill body. Reference it directly in the prompt text.

```markdown
Review the file at $ARGUMENTS for security issues.
Focus on input validation, authentication, and injection vectors.
```

## Relative Paths with ${CLAUDE_SKILL_DIR}

Reference supporting files relative to the skill's location. Never use absolute paths that break across machines.

```markdown
Read the checklist at ${CLAUDE_SKILL_DIR}/checklists/security-review.md
and apply every item to the target file.
```

## Supporting File Conventions

Skills that need reference material, checklists, or templates must store them alongside the skill file or in a subdirectory.

```
skills/
  deploy-preview.md
  deploy-preview/
    environments.yml
    checklist.md
```

## Context Fork for Isolation

Skills run in the main conversation context by default. For skills that generate large output or perform exploratory work, use the context fork pattern to prevent context pollution.

Write the skill's instructions so the output is structured and minimal. Require bullet lists, file:line pairs, or tables instead of prose.

## Preamble Pattern for Cross-Cutting Concerns

When multiple skills share the same rules, extract them into a preamble file and reference it.

```markdown
Read and follow the rules in ${CLAUDE_SKILL_DIR}/preamble.md before proceeding.

Then: [skill-specific instructions]
```

The preamble contains shared constraints: output format, safety checks, quality gates. Each skill adds its domain-specific logic after the preamble.

## Rules

- One skill per file. No multi-purpose skills.
- Skill names use kebab-case: `deploy-preview`, not `deployPreview` or `deploy_preview`.
- Descriptions must be specific enough for automatic matching. "Do stuff" will never match. "Deploy a preview environment for the current branch" will.
- Never hardcode project-specific paths in global skills. Use `${CLAUDE_SKILL_DIR}` or accept paths via `$ARGUMENTS`.
- Test every skill manually before relying on it. Run it once, read the output, verify correctness.

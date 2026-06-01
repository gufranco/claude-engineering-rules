---
name: skill-new
description: Scaffold a new SKILL.md with the enforced frontmatter and 6-section template, then validate with the skill linter. Use when user says "new skill", "create a skill", "scaffold a skill", or asks to add a slash command. Do NOT use for editing existing skills (use Edit directly), for renaming a skill (use Bash mv + linter), or for deleting a skill (no skill required).
argument-hint: "/skill-new <kebab-case-name>"
allowed-tools: "Read, Write, Bash, AskUserQuestion"
user-invocable: true
sensitive: false
---

Meta-skill that creates new skills consistently. Produces a SKILL.md that passes `tools/lint-skills.py --strict` on first save, with placeholders that force the author to fill in the load-bearing parts.

## Overview

Hand-authored skills drift in shape. Some have argument hints, some do not. Some declare allowed tools, some do not. The 6-section template gets partially adopted. This skill removes the drift by scaffolding from a single source of truth and immediately validating the result.

## When to Use

- User says "new skill X", "scaffold skill", "create a slash command for X"
- A new repeatable workflow has emerged that justifies a slash command
- A retrospective surfaced a pattern that should become a skill

Do NOT use when:
- The behavior belongs in a rule, hook, or agent instead (consider first)
- The workflow is too project-specific to live in the global config
- An existing skill already covers the use case (extend it)

## Process

1. **Resolve name.** Accept a kebab-case identifier (e.g., `interview-me`). Reject names that already exist under [`skills/`](../). Reject names that conflict with an existing slash command vocabulary.
2. **Gather inputs.** Ask one question at a time, using `AskUserQuestion`:
   - One-line description (50+ characters, names the trigger phrases and the anti-scope)
   - Argument hint (example invocations)
   - Tool scope: which tools the skill needs (`allowed-tools`) OR which to deny (`disallowed-tools`)
   - User-invocable (`true` for slash commands the user types, `false` for skills the model auto-invokes)
   - Sensitive flag (`true` for destructive or privileged skills)
3. **Scaffold.** Create `skills/<name>/SKILL.md` with the frontmatter block and the six required headings. Each section gets a placeholder paragraph that names what belongs there.
4. **Validate.** Run `python3 tools/lint-skills.py --strict skills/<name>/SKILL.md`. Block return until the linter passes.
5. **Register.** If a new on-demand rule trigger applies, add an entry to [`rules/index.yml`](../../rules/index.yml). If the skill should appear in the README skill table, update it.

## Common Rationalizations

- "I will copy from another skill instead": copying introduces drift. Scaffold from the template.
- "I will fill the sections in later": the linter blocks merging until the sections exist. Fill them now.
- "I will skip the linter, the file is fine": strict mode catches missing fields you forgot. Run it.
- "The description is good enough at 20 characters": short descriptions fail discovery. Aim for 50+.

## Red Flags

- About to commit a skill where `argument-hint` is empty or absent
- About to commit a skill with neither `allowed-tools` nor `disallowed-tools`
- About to commit a skill missing one of the six required sections
- About to invoke this skill for editing an existing SKILL.md
- About to scaffold a skill whose name collides with an existing one

## Verification

- `python3 tools/lint-skills.py --strict skills/<name>/SKILL.md` returns 0
- README skill table updated if user-invocable
- [`rules/index.yml`](../../rules/index.yml) updated if the skill is triggered on-demand by keywords
- Frontmatter `name` matches the directory name exactly
- All six required sections present with non-empty bodies

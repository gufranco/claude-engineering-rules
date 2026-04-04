---
name: document-release
description: Post-ship documentation sync. Reads all project docs and cross-references the latest diff to find stale, missing, or outdated documentation. Identifies new features without docs, removed features still documented, changed APIs with stale examples, new env vars not in .env.example, and new CLI commands not documented. Use when user says "document release", "sync docs", "update docs after release", "docs drift", "stale documentation", "changelog polish", or wants to ensure documentation matches the current codebase after shipping. Do NOT use for generating READMEs from scratch (use /readme), code review (use /review), or incident reports (use /incident).
---

Post-ship documentation sync skill. Cross-references the latest code changes against all project documentation to identify drift, then offers to fix each stale section.

## Invocation

| Invocation | Action |
|-----------|--------|
| `/document-release` | Compare docs against changes since the last tag |
| `/document-release <N>` | Compare docs against the last N commits |
| `/document-release <ref>..<ref>` | Compare docs against a specific commit range |

---

## Steps

1. **Determine the diff range.** Identify what changed:
   - If no argument: find the most recent tag with `git describe --tags --abbrev=0` and diff from there to HEAD.
   - If a number: use `HEAD~<N>..HEAD`.
   - If a range: use it directly.
   - Run `git diff --name-only <range>` to get the list of changed files.
   - Run `git diff <range>` to get the full diff for content analysis.

2. **Inventory all documentation files.** Read every documentation source in the project:

   | File | Purpose |
   |------|---------|
   | `README.md` | Project overview, setup, usage |
   | `CONTRIBUTING.md` | Contribution guidelines |
   | `ARCHITECTURE.md` | System design and component relationships |
   | `CHANGELOG.md` | Release history |
   | `docs/` directory | All files recursively |
   | `CLAUDE.md` | Project-level AI instructions |
   | `.env.example` | Environment variable documentation |
   | `openapi.yaml` or `swagger.json` | API specification |

   Skip files that do not exist. Record which documentation files the project has.

3. **Cross-reference changes against documentation.** For each changed file in the diff, check:

   | Change type | What to check | Where to check |
   |-------------|--------------|----------------|
   | New exported function or class | Is it documented in API docs? | `docs/`, `README.md` |
   | New API endpoint | Is it in the API spec and README? | `openapi.yaml`, `README.md`, `docs/api/` |
   | New environment variable | Is it in `.env.example` with a description? | `.env.example`, `README.md` |
   | New CLI command or flag | Is it documented in usage instructions? | `README.md`, `docs/` |
   | Removed feature or endpoint | Is the old documentation still present? | All doc files |
   | Changed function signature | Are code examples still valid? | `README.md`, `docs/` |
   | New dependency | Is setup documented if it requires configuration? | `README.md` |
   | Changed configuration | Are config docs updated? | `README.md`, `docs/` |
   | New migration | Is the migration process documented? | `README.md`, `CONTRIBUTING.md` |
   | Architecture change | Does `ARCHITECTURE.md` reflect the new structure? | `ARCHITECTURE.md` |

4. **Compile findings.** For each documentation gap found:
   - State which documentation file is affected.
   - State what is missing or stale.
   - Reference the specific code change that created the gap.
   - Propose the documentation update.

5. **Polish CHANGELOG voice.** If `CHANGELOG.md` exists and has entries for the current release:
   - Rewrite entries to be user-facing: explain the value to the user, not the implementation detail.
   - Use present tense: "Adds support for..." not "Added support for...".
   - Group by: Added, Changed, Fixed, Removed, Security.
   - Remove internal jargon. A user reading the changelog does not know module names or internal service boundaries.

6. **Offer updates.** Present each finding and ask whether to apply the fix. Apply approved changes using the Edit tool.

### Output

```
## Documentation Release Report

**Diff range:** <range>
**Files changed:** <count>
**Docs files found:** <list>

### Gaps Found

| # | Doc file | Issue | Code reference |
|---|----------|-------|---------------|
| 1 | README.md | New env var `DATABASE_URL` not documented | src/config.ts:15 |
| 2 | .env.example | Missing `REDIS_HOST` | src/cache/redis.ts:3 |
| 3 | docs/api.md | Endpoint `/api/v2/users` not documented | src/routes/users.ts:42 |
| 4 | README.md | Removed `--legacy` flag still in usage section | Deleted in src/cli.ts |

### CHANGELOG Polish
<Rewritten entries in user-facing voice, grouped by category>

### Actions
Apply updates? [list each with y/n]
```

## Rules

- Never delete documentation content without confirmation. Follow `../../rules/documentation.md`.
- When updating docs, merge new content into existing structure. Never replace entire files.
- Preserve the existing heading hierarchy and formatting conventions of each documentation file.
- All timestamps in GMT.
- Prefix every `gh` or `glab` command with the appropriate token per `../../rules/github-accounts.md` or `../../rules/gitlab-accounts.md`.
- CHANGELOG entries must be written for end users, not developers. "Refactored the auth module" becomes "Improved login reliability."

## Related skills

- `/readme` -- Generate a README from scratch.
- `/ship release` -- Create a tagged release.
- `/review` -- Code review that may catch documentation gaps.
- `/retro` -- Session retrospective for process improvements.

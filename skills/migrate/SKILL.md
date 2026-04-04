---
name: migrate
description: Framework and library migration assistant. Detects current usage, identifies the migration path from official docs, generates a migration plan, and applies changes incrementally with testing between steps. Each step is a separate commit for easy rollback. Handles framework migrations, library swaps, major version upgrades, and language version upgrades. Use when user says "migrate", "upgrade", "swap library", "replace express with fastify", "upgrade to v5", "move from jest to vitest", or wants to change a framework, library, or major version. Do NOT use for dependency auditing (use /audit), code review (use /review), or planning without execution (use /plan).
---

Framework and library migration assistant. Applies changes incrementally with a separate commit per step and full test runs between steps, so any step can be rolled back independently.

## Invocation

| Invocation | Action |
|-----------|--------|
| `/migrate <from> <to>` | Migrate from one library/framework to another |
| `/migrate <library> <version>` | Upgrade a library to a specific major version |

Examples:
- `/migrate express fastify`
- `/migrate jest vitest`
- `/migrate react 19`
- `/migrate node 22`
- `/migrate typescript 5.5`

---

## Steps

1. **Detect current state.** Analyze the current usage of the source library or framework:
   - Read the manifest file to find the current version.
   - Search the codebase for import statements and usage patterns.
   - Count affected files: `grep -r "import.*from '<source>'" --include="*.ts" --include="*.tsx" | wc -l`
   - Identify configuration files specific to the source.
   - List plugins, extensions, or addons that depend on the source.

2. **Research the migration path.** Gather migration guidance:
   - Check for official migration guides from the target library or framework.
   - Identify breaking changes between the source and target versions.
   - Map source APIs to target equivalents.
   - Identify features with no direct equivalent that require redesign.

3. **Generate migration plan.** Create a step-by-step plan:

   | Step | Description | Risk | Rollback |
   |------|------------|------|----------|
   | 1 | Install target, keep source as fallback | Low | Remove target from dependencies |
   | 2 | Migrate configuration files | Medium | Restore config from git |
   | 3 | Migrate utility and helper modules | Low | Revert commit |
   | 4 | Migrate core application code | High | Revert commit |
   | 5 | Migrate test files | Medium | Revert commit |
   | 6 | Remove source dependency | Low | Re-add to manifest |
   | 7 | Clean up: remove compatibility shims | Low | Revert commit |

   Present the plan and wait for approval before proceeding.

4. **Execute each step.** For every step in the plan:
   a. Make the code changes for this step only.
   b. Run the formatter.
   c. Run the linter. Fix any new warnings.
   d. Run the full test suite. If tests fail because of the migration, fix them as part of this step.
   e. Run the build. Verify zero errors.
   f. Commit with a descriptive message: `refactor(<scope>): migrate <component> from <source> to <target>`.
   g. Report the step result before proceeding to the next.

5. **Verify final state.** After all steps complete:
   - Confirm the source library is no longer in the dependency manifest.
   - Confirm no import statements reference the source.
   - Run the full test suite one final time.
   - Run the build one final time.
   - Report the migration summary.

### Output per step

```
## Step <N>/<total>: <description>

**Files changed:** <count>
**Tests:** <passed>/<total>, <failed> failures
**Build:** pass/fail
**Commit:** <hash> <message>
```

### Final output

```
## Migration Complete

**Source:** <library@version>
**Target:** <library@version>
**Steps completed:** <N>/<total>
**Total files changed:** <count>
**Total commits:** <count>

### Verification
- [ ] Source removed from dependencies
- [ ] No source imports remain
- [ ] All tests pass
- [ ] Build succeeds
- [ ] No linter warnings

### Breaking Changes Applied
| Change | Files affected | How resolved |
|--------|---------------|-------------|
| <API change> | <count> | <approach taken> |

### Manual Follow-up
- <Any items requiring manual verification or testing>
```

## Rules

- Never execute without presenting the plan first. Wait for approval.
- Each step must be a separate commit. Never batch multiple migration steps into one commit.
- Run the full test suite after every step, not just affected tests.
- If a step fails tests and the fix is non-trivial, stop and report. Do not continue with a broken intermediate state.
- When the source and target have different paradigms, do not force a 1:1 mapping. Redesign the affected code to be idiomatic in the target.
- Preserve all existing test coverage. Migration must not reduce the test count or coverage percentage.
- Do not add the target library without checking if it is already a dependency.
- Follow `../../rules/code-style.md` dependency evaluation criteria when the migration involves choosing between alternatives.
- Prefix every `gh` or `glab` command with the appropriate token per `../../rules/github-accounts.md` or `../../rules/gitlab-accounts.md`.

## Related skills

- `/plan` -- Plan the migration without executing it.
- `/audit` -- Check for vulnerabilities in the target library before migrating.
- `/test` -- Run the test suite independently.
- `/ship commit` -- Commit migration steps.
- `/review` -- Review the migration diff.

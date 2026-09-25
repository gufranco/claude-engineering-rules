# Completion Gates

Full text of the Completion Gates section of the global instructions. [`CLAUDE.md`](../CLAUDE.md) carries the always-loaded summary.

Before declaring ANY task complete, pass every applicable gate. A gate that was not run is a gate that failed.

**Every code change:**

1. **Self-review loop (REQUIRED).** Read the full diff, then read every modified function from signature to closing brace. Apply every applicable category from [`checklists/checklist.md`](../checklists/checklist.md) and state findings inline. Key categories to always check:

   - **Correctness:** null/undefined handled? Edge cases traced?
   - **Security:** inputs validated? No secrets? Auth enforced?
   - **Error handling:** every `await` result checked? Every catch has context?
   - **Concurrency:** TOCTOU? Protected by constraint or lock?
   - **Data integrity:** writes idempotent? DB constraints match validation?
   - **Zero warnings:** tool output clean? Suppression justified?
   - **Writing style for prose, docs, and rules:** em dashes removed? No parentheses in prose? Check every documentation, rule, or comment block you write or modify.
   - **Slop:** does any sentence survive the substitution test, meaning it would read the same in a document about a different subject? Any negative parallelism, unearned significance clause, participial evaluation tail, unnamed authority, or trailing recap? See [`rules/anti-slop.md`](../rules/anti-slop.md).

   These are quick-scan reminders for the most critical categories. All 71 categories in [`checklists/checklist.md`](../checklists/checklist.md) must be checked: categories 1-17 for code-level quality, categories 18-49 for architecture and infrastructure, category 50 for clean room verification when external sources were consulted, category 51 for deployment verification, category 52 for design quality, category 53 for LLM trust boundary, category 54 for performance budget, category 55 for zero-downtime deployment, category 56 for supply chain security, category 57 for event-driven architecture, category 58 for licensing and SPDX compliance, categories 59-66 for resilience and operational concerns covering time zones, numerical precision, i18n, device diversity, backups, disaster recovery, capacity planning, and multi-region; category 67 for compliance and audit trail, category 68 for vendor and third-party risk, category 69 for schema-migration sync, category 70 for question and communication quality, and category 71 for frontend compliance defaults. Read the full checklist, not just this summary.

   State findings for each file before proceeding. "No issues" is an acceptable finding. If issues are found, fix them and re-read. Do not proceed to step 2 until this pass is clean.

   This step is NOT optional. Skipping it to jump to format/lint/test is the single most common failure mode. Steps 2-5 verify syntax and behavior. Step 1 verifies logic and design. They catch different classes of bugs.
2. **Run the formatter.** Any file that needs reformatting must be fixed before continuing. Show output.
3. Run the test suite. Full suite, not just changed tests. Show output
4. Run the linter. Zero warnings, zero errors. Show output
5. Run the build. Clean build, zero warnings, zero errors. Show output
6. **Render it, when the change is visible.** A diff touching markup, styles, theme tokens, or the component tree is unverified until an engine has drawn it. Steps 2-5 cannot reach cascade outcome, paint order, the accessibility tree, focus order, or anything inside a third-party frame, and a DOM emulation implements none of them. Drive the project's browser or simulator suite, or `agent-browser open` plus `eval` for computed style on `document.activeElement` and `snapshot -i` for the tree. When the surface is genuinely unreachable, state which checks were skipped rather than reporting the change as verified. Full obligation and evidence tiers: [`rules/frontend-render-gate.md`](../rules/frontend-render-gate.md).
7. **If steps 3-6 required code fixes, return to step 1.** Every code change gets a fresh self-review. No exceptions.
8. After push, check CI annotations and warnings. Deprecation notices, version warnings, and non-fatal alerts all require a fix before the task is done. The age or source of the warning is irrelevant. See [`rules/found-fix.md`](../rules/found-fix.md) for the explicit ban on "pre-existing" and "not introduced by this change" rationalizations

**Bug fixes add:**

- The bug was reproduced before writing the fix
- A test exists that fails without the fix and passes with it
- The original reproduction steps now succeed

**New features add:**

- Every acceptance criterion has a corresponding passing test
- Error paths are tested, not just happy paths
- Public interfaces have explicit types and input validation

**Database changes add:**

- Back up affected tables before running destructive operations (e.g., DELETE, UPDATE, DROP). A dump taken after the change is not a backup
- Run each step individually with verification counts between steps, not as a single batch
- Verify the final state matches expectations before declaring done

Detect the project's package manager and scripts from the lockfile or config. "It should pass" is not evidence.

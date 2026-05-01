---
name: breaking-change
description: API breaking change management. Identifies all consumers of a changing API, generates a deprecation plan with timeline, creates the new API version alongside the old one, adds deprecation headers, and drafts a migration guide. Use when user says "breaking change", "deprecate API", "API migration", "version the API", "consumer migration", "sunset endpoint", or needs to change an API that has consumers. Do NOT use for non-breaking API changes, code review (use /review), or general planning (use /plan).
sensitive: true
---
Breaking change management that finds every consumer of the changing interface, creates the new version alongside the old one, adds deprecation signals, and drafts a migration guide. Ensures both versions work simultaneously during the transition period.

## When to use

- When changing a public API endpoint in a way that breaks existing consumers.
- When renaming or restructuring a function signature used by multiple callers.
- When altering a database column, event schema, or config key that other services depend on.
- When sunsetting an endpoint or feature that external clients rely on.

## When NOT to use

- For additive, non-breaking API changes. Just add the new field or endpoint.
- For code review of existing changes. Use `/review` instead.
- For general implementation planning. Use `/plan` instead.
- For internal refactors with no external consumers.

## Arguments

This skill accepts arguments after `/breaking-change`:

- `<endpoint-or-function>`: specify the interface that is changing. Example: `/breaking-change POST /api/orders`, `/breaking-change calculatePrice`.
- `--plan-only`: generate the deprecation plan and migration guide without implementing any changes.

## Steps

1. **Identify the changing interface.** Parse the argument to determine what is changing. Classify the type:
   - REST API endpoint: a route with an HTTP method.
   - Function or method signature: a public export consumed by other modules.
   - Event schema: a message format published to a queue or event bus.
   - Database column or table: a schema element referenced by queries.
   - Configuration key: an environment variable or config property.
   - Read the current definition of the interface. Record the current contract: parameters, return type, response shape, or schema.

2. **Find all consumers.** Use a combination of grep and code tracing to locate every reference:
   - For API endpoints: search for the URL path in `fetch`, `axios`, `got`, `request`, `href`, `action`, `trpc`, and test files. Search client SDKs if they exist. Search OpenAPI or Swagger spec files.
   - For functions: search for import statements, direct calls, and re-exports. Check test files, barrel exports, and dynamic references.
   - For event schemas: search for publish and subscribe calls referencing the event name or type.
   - For database columns: search the ORM schema, all service files, migration files, seed files, and raw queries.
   - For config keys: search `.env.example`, CI configs, Docker files, Terraform files, and all `process.env` or config reads.

3. **Classify consumers by scope.**
   - **Internal, same repo:** files in the current repository that reference the interface. These can be migrated in the same PR.
   - **Internal, other repos:** services owned by the same team in different repositories. These need coordinated migration.
   - **External, third-party:** consumers outside your control. These need a public deprecation notice and migration window.

   Present the consumer list:

   ```
   ### Consumers of <interface>

   **Internal (this repo):** N references
   - src/controllers/order.controller.ts:34
   - src/services/billing.service.ts:78
   - tests/order.integration.test.ts:12

   **Internal (other repos):** estimated N (check with team)
   - mobile-app (if known)
   - admin-dashboard (if known)

   **External:** unknown (check API access logs if available)
   ```

4. **Generate the deprecation plan.** Create a three-phase plan:

   **Phase 1, coexistence, starting now:**
   - Create the new version of the interface alongside the old one.
   - Both versions work simultaneously.
   - Add deprecation signals to the old version:
     - HTTP APIs: `Deprecation` header per RFC 9745, `Sunset` header per RFC 8594 with a concrete date, `Link` header pointing to migration docs.
     - Functions: JSDoc `@deprecated` tag with the replacement and removal version.
     - Events: add a deprecation field to the schema metadata.
   - Migrate all internal consumers in this repo to the new version.
   - Update documentation to reference the new version as primary.

   **Phase 2, migration window, starting after Phase 1 ships:**
   - Monitor usage of the old version. Check access logs, analytics, or API gateway metrics.
   - Notify remaining consumers with specific migration instructions.
   - Provide a deadline: the sunset date from the `Sunset` header.
   - Offer office hours or support for complex migrations.

   **Phase 3, removal, after the sunset date:**
   - Verify zero traffic on the old version.
   - Remove the old version.
   - Update all documentation.
   - Clean up any compatibility shims.

5. **If `--plan-only` was passed, stop here.** Present the plan and consumer list. Do not implement.

6. **Implement Phase 1.** Create the new version:
   - For API endpoints: add a new route. If using URL versioning, add `/v2/...`. If using header versioning, add content negotiation. Keep the old route working with deprecation headers.
   - For functions: create the new function with the updated signature. Add `@deprecated` to the old function. Have the old function call the new one internally if possible to avoid logic duplication.
   - For event schemas: publish both the old and new formats during the transition. Consumers can migrate at their own pace.
   - For database columns: add the new column. Backfill data. Write to both columns during transition. Read from the new column.

7. **Add deprecation signals to the old version.**
   - HTTP `Deprecation: true` header on every response from the old endpoint.
   - HTTP `Sunset: <date>` header with the planned removal date.
   - HTTP `Link: <url>; rel="deprecation"` header pointing to the migration guide.
   - Log a warning when the old version is called, including the caller identity if available.
   - For functions: `@deprecated Use newFunction() instead. Will be removed in vX.Y.Z.`

8. **Migrate internal consumers.** Update every reference found in step 2 that is in this repo:
   - Replace imports and calls to use the new version.
   - Update test files to test the new version.
   - Keep tests for the old version to verify backward compatibility during the transition.

9. **Draft the migration guide.** Create a document that covers:
   - What changed and why.
   - Side-by-side comparison of the old and new API.
   - Step-by-step migration instructions with code examples.
   - Timeline: when the old version will stop working.
   - Where to get help.

   Format:

   ```
   ## Migration Guide: <interface>

   ### What changed
   <One paragraph explaining what changed and the motivation.>

   ### Before and after

   **Old (deprecated):**
   <code example>

   **New:**
   <code example>

   ### How to migrate
   1. <step>
   2. <step>
   3. <step>

   ### Timeline
   - Phase 1 (now): both versions work. Old version returns deprecation headers.
   - Phase 2 (<date>): migration support period. Reach out if you need help.
   - Phase 3 (<sunset date>): old version removed.

   ### Questions
   Contact <team/channel>.
   ```

10. **Create a tracking issue.** List all known consumers and their migration status.
    - GitHub: `GH_TOKEN=$(gh auth token --user <account>) gh issue create --title "Track migration: <interface> v1 to v2" --body "<consumer list with checkboxes>"`
    - GitLab: `GITLAB_TOKEN=<token> GITLAB_HOST=<host> glab issue create --title "Track migration: <interface> v1 to v2" --description "<consumer list>"`

11. **Commit the changes.** Use the conventional commit format with the breaking change indicator:
    ```
    feat(api)!: add v2 of <endpoint>, deprecate v1

    New version created alongside the old one. Old version returns
    Deprecation and Sunset headers. Internal consumers migrated.

    BREAKING CHANGE: <description of what changed for consumers>
    ```

## Rules

- Never remove the old API in the same PR as the new one. Both must coexist.
- Always have both versions working simultaneously before merging.
- Always add deprecation headers to the old version. Silent deprecation causes surprise breakage.
- Always migrate internal consumers before expecting external consumers to migrate.
- Always include a sunset date. "Eventually" is not a timeline.
- Always prefix `gh` commands with `GH_TOKEN` per the github-accounts rule.
- Always prefix `glab` commands with `GITLAB_TOKEN` and `GITLAB_HOST` per the gitlab-accounts rule.
- When the old function can delegate to the new one, do so to avoid duplicating business logic.
- When a database column is changing, always backfill existing data. Empty new columns alongside populated old columns cause bugs.
- The migration guide must include code examples. Text-only instructions are insufficient.

## Related skills

- `/plan` - General implementation planning for complex features.
- `/review` - Review the breaking change PR before shipping.
- `/ship` - Commit and create the PR for the breaking change.
- `/deploy` - Deploy and monitor the breaking change in production.

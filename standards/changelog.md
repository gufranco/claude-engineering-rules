# Changelog

## Core Rule

Changelogs are for users, not developers. Every entry must describe what changed from the user's perspective. Implementation details belong in commit messages and PR descriptions, not in the changelog.

## Entry Format

Lead with what users can now DO. The verb comes first.

```
# Good: user-centric, action-first
- Create quotes directly from the job detail page
- Filter invoices by date range and payment status
- Export dispatch board data as CSV

# Bad: developer-centric, implementation-focused
- Added QuoteService.createFromJob() method
- Implemented date range filter component
- Refactored export module to support CSV
```

## Entry Quality Test

Each entry must pass this test: would a user who reads this line want to try the feature? If the answer is no, rewrite it or move it to the internal section.

## Sections

Separate user-facing changes from internal changes. Users scan the top section. Developers check the bottom when debugging.

```markdown
## [1.4.0] - 2026-04-04

### What's New
- Create quotes directly from the job detail page
- Filter invoices by date range and payment status

### Improvements
- Job list loads 40% faster on accounts with 10,000+ records
- Date picker respects the account's locale setting

### Fixes
- Fixed: PDF export no longer cuts off long address lines
- Fixed: dispatch board shows correct timezone for remote teams

### Internal
- Migrated quote service to hexagonal architecture
- Upgraded date-fns from 3.x to 4.x
- Added database indexes for invoice date range queries
```

## Section Definitions

| Section | Content | Audience |
|---------|---------|----------|
| What's New | New capabilities users did not have before | Users |
| Improvements | Existing features that work better now | Users |
| Fixes | Bugs that are resolved | Users |
| Breaking Changes | Changes that require user action to upgrade | Users |
| Deprecated | Features that will be removed in a future version | Users |
| Internal | Refactors, dependency upgrades, infrastructure changes | Developers |

## Version Tagging

Follow semantic versioning strictly.

| Change type | Version bump | Example |
|-------------|-------------|---------|
| Breaking API or behavior change | Major | 2.0.0 |
| New feature, backward compatible | Minor | 1.4.0 |
| Bug fix, no new features | Patch | 1.3.1 |

Tag format: `v1.4.0`. Always prefix with `v`. Always use three numbers.

## Date Format

Use ISO 8601: `YYYY-MM-DD`. No other format.

## Writing Rules

- One line per entry. No multi-line descriptions in the changelog.
- Start with a verb: "Create", "Filter", "Export", "Fix", not "Added ability to" or "Users can now".
- No ticket IDs in the changelog. Link them in the PR description.
- No author names or attribution.
- Keep entries under 100 characters. If it needs more, the scope is too broad for one entry.
- Prefix fix entries with "Fixed:" to distinguish them visually from features.

## Maintenance

- Update the changelog in the same PR as the code change, not retroactively.
- The "Unreleased" section at the top collects changes between releases.
- When cutting a release, move entries from "Unreleased" to the new version section.

## Release Notes

The release notes for a version are that version's changelog section. `/ship release` builds them in this order:

1. When the changelog has Unreleased entries, those entries are the notes. Move them under the new version heading, using the heading format the file already uses.
2. When the changelog is hand-written, a tool never regenerates it or rewrites its existing entries.
3. When no changelog exists or Unreleased is empty, draft from the commits since the last tag. Conventional commit types pick the version bump and locate the changes, and every entry is then written fresh for users per [Entry Format](#entry-format).

Three rules govern a draft:

- **User-facing only.** An internal refactor, a test, or a CI change goes in Internal, or nowhere when nobody outside the team would read it.
- **Related changes grouped.** Five commits that build one feature are one entry, never five.
- **Never a list of commit subjects.** A commit subject is written for maintainers and names how something was made. An entry names what a user can now do and why it changed.

Provenance: 2026-10-12, owner request. Adopted from the sandcastle pre-release skill, which reviews changesets as user-facing, grouped, and distinct from commit messages.

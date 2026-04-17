# Documentation Preservation

## Core Rule

When any skill or automated process modifies a documentation file, no existing valid information may be lost.

## Procedure

1. **Read the full file** before making any changes.
2. **Merge, do not replace.** New content is added to or updated within the existing structure. Never overwrite the file with only the new output.
3. **Preserve valid sections.** Sections that are still accurate and relevant stay intact.
4. **Flag conflicts.** If new content contradicts existing content, surface both versions and ask. Do not silently replace.
5. **Maintain structure.** Respect the existing heading hierarchy, ordering, and formatting conventions.

## What Counts as Valid

- Information that reflects the current state of the codebase, configuration, or architecture.
- Sections added manually by the user that are not outdated.
- Links, badges, and metadata that are still functional.

## What Can Be Removed

- Information that is demonstrably outdated: references to deleted files, removed features, or old versions.
- Duplicate content that the new output covers more accurately.
- Placeholder text that the new content replaces with real data.

When in doubt, keep the existing content and ask.

## Content Migration

When moving content from one file to another:

1. **Count items before and after.** Use grep to count discrete items in the source before migration and in the destination after. The counts must match.
2. **Diff the source.** After migration, every removed line must have a corresponding line in the destination or an explicit reason for removal.
3. **Categorize omissions.** Items intentionally excluded must be documented. Silent drops are bugs.

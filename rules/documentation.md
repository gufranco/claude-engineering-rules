# Documentation Preservation

## Core Rule

When any skill or automated process modifies a documentation file (README, docs, guides, changelogs), no existing valid information may be lost.

## Procedure

1. **Read the full file** before making any changes. Record all existing sections and their content.
2. **Merge, do not replace.** New content from skills is added to or updated within the existing structure. Never overwrite the entire file with only the new output.
3. **Preserve valid sections.** Sections that are still accurate and relevant stay intact, even if they were not part of the skill's output.
4. **Flag conflicts.** If new content contradicts existing content, surface both versions and ask which one to keep. Do not silently replace.
5. **Maintain structure.** Respect the existing heading hierarchy, ordering, and formatting conventions of the file.

## What Counts as Valid

- Information that reflects the current state of the codebase, configuration, or architecture.
- Sections added manually by the user that are not outdated.
- Links, badges, and metadata that are still functional.

## What Can Be Removed

- Information that is demonstrably outdated: references to deleted files, removed features, or old versions.
- Duplicate content that the new output covers more accurately.
- Placeholder text that the new content replaces with real data.

When in doubt, keep the existing content and ask.

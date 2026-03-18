---
name: retro
description: Analyze the conversation for corrections, preferences, and recurring patterns, then propose additions to the Claude configuration.
---

Analyze the current conversation to extract directives, corrections, preferences, and recurring mistakes, then propose concrete additions to the Claude Code configuration so the same issues do not happen again.

## When to use

- At the end of a significant multi-step session.
- After a session where the user corrected your behavior more than once.
- When the user explicitly asks you to analyze what went wrong or what to remember.
- **Proactively**: after completing significant work, run this analysis automatically (see the "Session Retrospective" rule in CLAUDE.md).

## When NOT to use

- After trivial one-shot tasks with no corrections or preferences expressed.
- When the conversation was purely informational with no implementation work.

## Arguments

This skill accepts optional arguments after `/retro`:

- No arguments: analyze the full conversation.
- `--dry-run`: show proposals without offering to write them.
- `--memory-only`: only update memory files, skip rule/CLAUDE.md proposals.

## Steps

### 1. Scan the conversation

Read through the entire conversation and extract:

| Category | What to look for | Example |
|----------|-----------------|---------|
| **Corrections** | User told you to stop doing X or start doing Y | "Don't add comments to code you didn't write" |
| **Preferences** | User expressed how they want things done | "I prefer single-color bars, not stacked" |
| **Repeated mistakes** | Same type of error appeared more than once | Forgetting platform compatibility three times |
| **Architectural decisions** | Decisions about the project that should persist | "Dashboard should be compact, max 56x28" |
| **Tool/workflow preferences** | How the user wants to interact with you | "Always run tests before declaring done" |
| **Project-specific knowledge** | Facts about the codebase learned during the session | "macOS stat needs /usr/bin/stat to bypass GNU" |

### 2. Deduplicate and diagnose against existing configuration

For each finding, read every potentially related file before drawing conclusions:

1. `~/.claude/CLAUDE.md`
2. `~/.claude/rules/*.md` (read each file, not just the index)
3. Project-level `CLAUDE.md` files
4. Memory files in `~/.claude/projects/*/memory/`

For each finding, answer two questions:

**Does it already exist?**

- If no existing coverage: mark as **New**, proceed to classification.
- If fully covered: skip it entirely. Do not re-add.
- If partially covered: mark as **Strengthen**, propose the specific addition that closes the gap.

**If it exists, why wasn't it respected in this session?**

This is mandatory when a finding matches an existing rule. Skipping this question means the same violation will happen again. Diagnose one of:

| Root cause | Action |
|------------|--------|
| Rule is vague or uses weak language ("should", "consider") | Rewrite with "must", add a concrete example that makes the boundary clear |
| Rule exists but has no example showing the wrong path | Add a bad/good example that matches this session's violation |
| Rule is buried inside a long section and easy to miss | Extract to a top-level bullet, or add a cross-reference from CLAUDE.md |
| Rule is in memory but applies universally | Move it to `~/.claude/rules/` or `~/.claude/CLAUDE.md` |
| Rule was correct but the context in this session was genuinely ambiguous | Add a clarifying note or edge-case handling to the rule |

Present the diagnosis as part of the finding row. "Rule exists but was vague" is a finding, not a reason to skip.

### 3. Classify each finding

Assign each unique finding to a destination. **`~/.claude/` is always the first choice.** Memory is the last resort, reserved only for facts that are physically impossible to apply outside a specific codebase.

Apply the classification gate in order. Stop at the first destination that fits:

1. **`~/.claude/CLAUDE.md`**: universal behavioral change, writing style, communication preference, workflow rule. Examples: "Use GMT in reports", "Always provide UI walkthroughs for instructions".
2. **`~/.claude/rules/*.md`** (new or existing file): domain-specific convention with enough detail to warrant its own section. Examples: new testing convention, new code style rule, new API design pattern.
3. **Skill update (`~/.claude/skills/<name>/SKILL.md`)**: change to how a specific skill operates. Example: "/commit should also check for X".
4. **Memory file**: only when the finding is a concrete, project-specific fact that would be misleading if applied to any other codebase. Infrastructure IDs, team member names, architecture choices for one specific repo. Examples: "Aurora cluster ID is database", "ECS cluster name is webservices".
5. **No action**: one-time context, not a pattern. Example: "Fix the typo on line 42".

**Hard rule:** if the finding describes behavior, a preference, or a recurring mistake, it goes in `~/.claude/`. Memory does not change behavior. Only `~/.claude/` files do. If you find yourself writing a behavioral rule into a memory file, stop and reclassify it.

**Classification check before writing:** ask "Could this finding cause the same problem in a completely different project?" If yes: `~/.claude/`. If the answer is "only if that project happens to use the same database/repo/service": memory.

### 4. Present findings

Show a summary table:

```
## Session Retrospective

### Findings

| # | Finding | Source | Destination | Status |
|---|---------|--------|-------------|--------|
| 1 | <description> | <where in conversation> | <file to update> | New / Strengthen |
| 2 | ... | ... | ... | ... |

### Proposed Changes

#### 1. <destination file>
<what to add or change, with the exact text>

#### 2. <destination file>
<what to add or change, with the exact text>
```

### 5. Apply changes

After presenting the proposals:

- Ask the user which changes to apply. Offer "All", "Pick individually", or "None".
- For each approved change, write or edit the target file.
- If any change touches a file inside `~/.claude/`, update `~/.claude/README.md` to reflect it.
- Show a final summary of what was written and where.

### 6. Verify

- Read each modified file to confirm the changes are present and correctly placed.
- If a rules file was updated, verify it does not contradict existing rules in other files.

### 7. Offer commit and push for `~/.claude/` changes

If any file inside `~/.claude/` was written or modified, ask the user:

> "Do you want to commit and push the changes made to `~/.claude/`?"

If the user says yes:

1. `cd ~/.claude`
2. Run `git status` to show exactly which files changed.
3. Stage only the modified files (never `git add .` or `git add -A`).
4. Commit using conventional format: `chore(claude): <short description of what changed>`.
5. Push: `git push`.
6. Confirm the push succeeded.

If the user says no, skip silently. Do not offer again.

## Rules

- Never write a rule that contradicts an existing one. If there is a conflict, present both and ask the user to choose.
- Never add duplicate content. If the finding already exists, skip it or propose strengthening the existing text.
- Keep proposals concise. Match the style of the target file. A memory entry is 1-2 lines. A CLAUDE.md rule is a bullet point. A rules file section has a heading and a few bullets or a table.
- Do not invent findings. Every proposal must trace back to something the user said or a mistake that actually happened in the conversation.
- If `--dry-run` was passed, present findings and proposals but do not offer to write them.
- If `--memory-only` was passed, only propose memory file updates, skip CLAUDE.md and rules.
- When running proactively at end of session, keep it brief. Skip the full table for sessions with zero or one finding. A simple "No recurring patterns to capture from this session" is enough.

## Related skills

- `/assessment` - Architecture audit for implementations.
- `/review` - Code review for PRs and branches.
- `/commit` - May trigger retro when `--pipeline` reveals recurring CI issues.

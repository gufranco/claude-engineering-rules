---
name: resolve
description: Guided merge conflict resolution with verification. Shows each conflict with context from both branches, suggests resolution based on understanding both changes, verifies tests pass after resolution, and checks that no functionality was lost. Use when user says "resolve conflicts", "merge conflict", "fix conflicts", "rebase failed", "conflict resolution", or has merge conflicts to resolve. Do NOT use for general debugging (use /investigate), code review (use /review), or git workflow questions.
---

Interactive conflict resolution that understands the intent behind each side of a conflict. Resolves conflicts one at a time with test verification after all conflicts are resolved.

## Arguments

- No arguments: detect and resolve conflicts in the current working tree.

## Process

### Step 1: Detect conflict state

Run `git status` to find all conflicted files. If no conflicts exist, check whether a rebase or merge is in progress:

```
git status
ls .git/MERGE_HEAD 2>/dev/null
ls .git/rebase-merge 2>/dev/null
```

If no conflicts and no in-progress operation, inform the user and exit.

### Step 2: List all conflicted files

Present the full list of conflicted files with their conflict type:

| File | Type |
|------|------|
| src/auth/login.ts | Both modified |
| src/api/routes.ts | Both modified |
| src/config/db.ts | Deleted by theirs, modified by ours |

### Step 3: Resolve each file

For each conflicted file, in order:

#### 3a. Read the conflict

Read the full file. Identify each conflict block marked by `<<<<<<<`, `=======`, `>>>>>>>`.

#### 3b. Understand both sides

For each conflict block:

1. Read the "ours" section: the changes from the current branch.
2. Read the "theirs" section: the changes from the incoming branch.
3. Check the git log for both branches to understand what each change was trying to accomplish:

```
git log --oneline -5 HEAD -- <file>
git log --oneline -5 MERGE_HEAD -- <file>
```

If this is a rebase, use `REBASE_HEAD` instead of `MERGE_HEAD`.

State what each side intended: "Our branch added input validation to the login handler. Their branch refactored the handler to use a service layer."

#### 3c. Choose a resolution strategy

| Situation | Strategy |
|-----------|----------|
| Changes are in different logical areas that happen to touch the same lines | Combine both changes |
| One side is a superset of the other | Take the more complete version |
| Both sides changed the same logic differently | Merge both intents into a single implementation |
| One side deleted code the other modified | Understand why it was deleted. If the deletion was intentional, keep the deletion. If the modification is important, keep the modification |
| Formatting-only conflict | Take whichever matches the project's formatter output |

#### 3d. Apply the resolution

Remove the conflict markers. Write the resolved content. Explain what was kept and what was discarded.

### Step 4: Stage resolved files

After all conflicts in a file are resolved:

```
git add <file>
```

Repeat Steps 3-4 for every conflicted file.

### Step 5: Verify with tests

Run the full test suite. This catches resolutions that compile but break behavior.

If tests fail:

1. Identify which resolution likely caused the failure by examining the test error and the resolved files.
2. Re-read the conflicting change.
3. Re-resolve that specific conflict with a different approach.
4. Run tests again.

### Step 6: Complete the operation

Continue the interrupted git operation:

- For merge: `git commit` to finalize the merge commit.
- For rebase: `git rebase --continue` to apply the next commit.
- For cherry-pick: `git cherry-pick --continue`.

If more conflicts appear after continuing a rebase, return to Step 1.

### Step 7: Final verification

After the operation completes with no remaining conflicts:

1. Run the full test suite.
2. Run the linter.
3. Run the type checker.
4. Verify the branch builds cleanly.

## Rules

- Never lose functionality from either side of a conflict. If both sides added features, the resolution must include both features.
- Always explain what each side intended before resolving. A resolution without understanding is a guess.
- Always test after resolution. A conflict that resolves cleanly at the text level can still break behavior.
- Never use `git checkout --ours` or `git checkout --theirs` on an entire file without reading every conflict in that file first. Blanket ours/theirs discards changes without review.
- When a conflict involves generated files like lockfiles, `package-lock.json`, or `pnpm-lock.yaml`, regenerate them instead of manually resolving: delete the file, run the package manager, and stage the result.
- If a conflict is too complex to resolve confidently, present both versions to the user with your analysis and ask for a decision. Do not guess.

## Related skills

- `/investigate` -- Debug test failures caused by a bad resolution.
- `/review` -- Review the merged result before pushing.
- `/ship commit` -- Commit after successful resolution.

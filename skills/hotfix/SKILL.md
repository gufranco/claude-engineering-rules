---
name: hotfix
description: Emergency production fix with expedited workflow. Creates a hotfix branch from the latest release tag, applies the minimal fix, runs critical tests, ships with expedited review, and backports to the main branch. Use when user says "hotfix", "production bug", "emergency fix", "prod is broken", "urgent fix", or needs to fix something in production immediately. Do NOT use for non-urgent bugs (use /investigate), feature work (use /plan), or general debugging (use /investigate).
sensitive: true
---
Expedited workflow for production emergencies. Prioritizes speed and minimal change over thoroughness. Every step is designed to get a safe fix deployed as fast as possible.

## Arguments

- No arguments: interactive mode. Ask what is broken in production.
- `<description>`: start the hotfix for the described issue.

## Process

### Step 1: Find the release baseline

Identify the latest release tag:

```
git describe --tags --abbrev=0
```

If no tags exist, use the current state of the main branch as the baseline.

### Step 2: Create the hotfix branch

```
git checkout -b hotfix/<description> <tag>
```

Use a short, descriptive branch name: `hotfix/null-pointer-checkout`, `hotfix/rate-limit-bypass`.

### Step 3: Identify the minimal fix

Read only the files directly related to the bug. Do not read surrounding code for context unless strictly necessary. Do not refactor anything.

The fix must be the smallest possible change that resolves the production issue. If two approaches exist and one touches fewer lines, choose that one.

### Step 4: Reproduce the bug

Write a test that demonstrates the failure. This test must:

- Fail on the current hotfix branch before the fix
- Pass after the fix is applied
- Be fast to run in isolation

If reproduction requires infrastructure that is not available locally, document the reproduction steps and skip to the fix.

### Step 5: Apply the fix

Implement the minimal change. Rules for hotfix code:

- No refactoring
- No renaming
- No style changes
- No dependency updates unless the dependency is the root cause
- No "while I'm here" improvements

### Step 6: Run critical tests

Run only the test files that cover the affected code, not the full suite. Speed matters.

```
# Run only affected test files
<test-runner> <affected-test-files>
```

If critical tests pass, proceed. If the full suite is fast, less than 2 minutes, run it. Otherwise, trust CI for the full suite.

### Step 7: Commit

```
fix(scope): <description>

Hotfix for v<version>. <Brief explanation of the root cause>.
```

### Step 8: Push and create PR

Push the hotfix branch. Create a PR targeting the release branch. If no release branch exists, target main.

Mark the PR as urgent in the title: `[HOTFIX] fix(scope): <description>`.

### Step 9: Backport to main

After the hotfix is merged to the release branch:

```
git checkout main
git pull origin main
git cherry-pick <hotfix-commit-hash>
```

Run tests on main to verify the cherry-pick applies cleanly. If conflicts exist, resolve them and verify.

### Step 10: Tag the patch release

```
git tag v<major>.<minor>.<patch+1>
git push origin v<major>.<minor>.<patch+1>
```

## Rules

- Minimal change only. The hotfix branch exists to fix one thing and nothing else.
- No scope creep. If you notice other issues while fixing, note them for later. Do not fix them now.
- Speed is the priority. Skip steps that do not contribute to getting the fix deployed safely.
- Backport must happen the same day. A fix that lives only on the release branch will be lost on the next release from main.
- Never skip the reproduction test. A hotfix without a test is a hotfix that can regress silently.
- If the fix is not obvious within 30 minutes, escalate. Call in another engineer. A wrong hotfix is worse than a slow hotfix.

## Related skills

- `/investigate` -- When the root cause is unclear and structured debugging is needed before the fix.
- `/ship commit` -- Commit the hotfix.
- `/incident` -- Document the incident after the fix is deployed.
- `/review` -- Expedited review of the hotfix PR.

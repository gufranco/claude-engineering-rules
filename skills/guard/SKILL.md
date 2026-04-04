---
name: guard
description: Combined safety mode for risky operations. Activates directory freeze, destructive command warnings, and scope enforcement simultaneously. Use when user says "guard", "safe mode", "freeze to this directory", "be careful", "restrict edits", or wants extra protection during a risky operation. Do NOT use for debugging (use /investigate), code review (use /review), or general editing.
---

Activates multiple safety protections at once to reduce the risk of accidental damage during sensitive operations.

## Arguments

| Invocation | Action |
|-----------|--------|
| `/guard <directory>` | Activate guard mode, freeze edits to the specified directory |
| `/guard` | Activate guard mode for the current project root |
| `/guard off` | Deactivate guard mode, remove all restrictions |
| `/guard status` | Show current guard state |

## Protections

Guard mode enables three protections simultaneously:

| Protection | What it does |
|-----------|-------------|
| **Freeze** | Restricts file edits to the specified directory. Writes to `~/.claude/.freeze-scope` with the frozen path. The `scope-guard.sh` hook enforces the boundary. |
| **Careful** | Warns before any destructive command: `rm`, `git reset`, `DROP`, `DELETE`, and patterns covered by the dangerous-command-blocker hook. |
| **Scope** | If a `plan.md` exists in the project's spec folder, compares every file edit against the planned file list. Warns when editing files not in the plan. |

## Process

### Activate

1. **Resolve the directory.** If a directory argument is given, resolve it to an absolute path. If no argument, use the project root from `git rev-parse --show-toplevel`.

2. **Verify the directory exists.** If it does not, abort with an error.

3. **Write the freeze scope.** Create `~/.claude/.freeze-scope` with the absolute path.

4. **Verify the hook.** Check that `../../hooks/scope-guard.sh` exists. If it does not, warn that freeze enforcement requires the hook to be configured.

5. **Check for plan.md.** Search for a spec folder with a `plan.md`:
   - Check `.claude/specs/*/plan.md` in the project root.
   - If found, read the planned file list for scope comparison.
   - If not found, skip scope protection and note it.

6. **Confirm activation.** State:
   - Frozen directory path.
   - Whether scope checking is active.
   - How to deactivate: `/guard off`.

### Deactivate

1. **Remove the freeze scope.** Delete `~/.claude/.freeze-scope` if it exists.

2. **Confirm deactivation.** State that all guard protections are removed.

### Status

1. **Check freeze scope.** Read `~/.claude/.freeze-scope` if it exists.
2. **Check for plan.md.** Search for an active plan.
3. **Report:**

   | Protection | Status |
   |-----------|--------|
   | Freeze | Active: `/path/to/directory` or Inactive |
   | Careful | Active: always on when guard is active |
   | Scope | Active: using `plan.md` at `/path` or Inactive: no plan found |

## Behavior While Active

When guard mode is active, every file edit and destructive command follows these checks:

1. **Before editing a file:**
   - Verify the file path is inside the frozen directory. If not, refuse the edit and state why.
   - If scope checking is active, verify the file is listed in `plan.md`. If not, warn and ask for confirmation before proceeding.

2. **Before running a destructive command:**
   - State the command and its potential impact.
   - Ask for explicit confirmation before executing.
   - Never run destructive commands silently while guard is active.

## Rules

- Guard mode is advisory for careful and scope protections. Freeze is enforced by the hook when configured.
- The `.freeze-scope` file contains exactly one line: the absolute directory path.
- Activating guard a second time with a different directory overwrites the previous freeze scope.
- Guard mode does not persist across sessions. It must be reactivated in each new session.
- Never auto-deactivate guard mode. Only `/guard off` or session end removes it.
- All paths must be absolute, never relative.

## Related Skills

- `/investigate --freeze` -- Debugging with freeze protection uses the same mechanism.
- `/plan` -- Creates the `plan.md` that scope checking uses.
- `/ship commit` -- Commit after completing guarded work.

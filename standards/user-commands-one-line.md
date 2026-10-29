# User Commands in One Line

## The Rule

Every reply that asks the user to run more than one command gives them a single line, built so that a failed or unexpected step stops everything after it. The line is ready to paste after the Claude Code `!` prefix.

## Why

The user runs these commands while working on something else. Separate blocks mean several pastes and the chance of running a cleanup after the step it depends on failed. One line is one paste. Chaining removes the pause between steps, though, so the line itself has to carry the safety that pause used to give: every gate is an exit code, never something the user reads.

## The Safe Shape

```text
! (set -euo pipefail && S=/abs/path && echo "== check" && <check> && echo "== change" && <change> && echo "== cleanup" && rm -rf "${S:?}/tmp")
```

| Part | Why |
|---|---|
| `( ... )` | A subshell, so strict mode and variables never leak into the user's shell |
| `set -euo pipefail` | An unset variable, a failed command, or a failed stage of a pipe stops the line |
| `&&` between steps | Explicit stop on failure, readable without knowing `set -e` |
| `S=/abs/path` once | A long path is typed once and can be checked |
| `echo "== step"` | The output reads in order, so the user can see which step failed |
| `"${S:?}/tmp"` | A recursive delete refuses to run when the variable is empty, instead of deleting from `/` |

## Gates

A check that protects a risky step must fail by exit code. Turn the condition into a command that exits non-zero when it does not hold:

| Condition | Gate |
|---|---|
| A file exists | `test -f "$S/run.sh"` |
| Output contains a value | `aws ... --output text \| grep -q '^1$'` |
| A count is what you expect | `test "$(cmd \| wc -l)" -eq 3` |
| A database precondition | a script mode that exits non-zero, such as `run.sh check` failing on a missing column |
| A clean tree | `test -z "$(git status --porcelain)"` |

When the decision needs human judgment, such as reading a list of rows before a production write, the check does not go in the same line as the change:

1. Run the read-only part yourself when you can, and read the result.
2. When you cannot, hand the check as its own line, and the change as its own line in the next turn, after the user has seen the result.

Each handoff is still one line.

## Bans Inside the Line

- `;` between steps outside strict mode: it runs the next step after a failure.
- `|| true`, `|| :`, or `2>/dev/null` on a gate: a silenced failure is not a gate.
- An unquoted variable, a relative path for a destructive step, a recursive delete without `${VAR:?}`.
- `sudo`, `--force`, `-f` on `git push`, or a `--dangerously-*` flag, unless the step cannot work without it and the sentence beside the line says why.
- A secret in the line itself. Read it inside the line from its store, as `V=$(aws secretsmanager ...)`, so it never reaches the screen or the shell history.

## Example

Wrong:

```text
! /path/run.sh check
! /path/run.sh backfill
! docker rm -v app-db app-cache
```

Right:

```text
! (set -euo pipefail && S=/path && echo "== check" && "$S/run.sh" check && echo "== backfill" && "$S/run.sh" backfill && echo "== cleanup" && docker rm -v app-db app-cache)
```

Here `run.sh check` exits non-zero on a bad state, so the backfill cannot run after a failed check.

## Exceptions

- A single command needs no chaining, but still follows the bans above.
- An interactive step that must read a terminal, such as a login, cannot run through `!`; give the user one line to run in their own terminal.
- Commands shown for reference in documentation or a runbook are not commands handed to the user to run now.

## Enforcement

[`hooks/user-commands-one-line.py`](../hooks/user-commands-one-line.py) is a Stop hook. It reads the reply that ends the turn and blocks it when two or more lines begin with `! `, when a `! ` line joins steps with `;` outside strict mode, when it silences a failure with `|| true` or `|| :`, or when it deletes recursively from a path built from a variable without `${VAR:?}`. It does not fire on a turn a Stop hook already continued. Bypass with `USER_COMMANDS_ONE_LINE_DISABLE=1` in the parent shell, or a TTL-bound entry in the shared bypass registry.

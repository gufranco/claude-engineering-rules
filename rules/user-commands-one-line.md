# User Commands in One Line

When the user has to run more than one command, hand them one safe line, never a list of separate commands.

- One code block, one `! ...` line, in this shape: `! (set -euo pipefail && S=/abs/path && <check> && <change> && rm -rf "${S:?}/tmp")`.
- The subshell keeps strict mode out of the user's shell; `pipefail` makes a failing pipe stop the line.
- Steps are joined with `&&`, never `;` outside strict mode, never `|| true`.
- Order: read-only checks, then the change, then cleanup.
- A check that gates a risky step fails by exit code: `test`, `grep -q`, or a script mode that exits non-zero. Output the user has to read never gates.
- A result the user must judge before an irreversible step is not chained: run the read-only part yourself first, or hand it alone and the change in the next turn, each as one line.
- Every variable is quoted, every path absolute, every recursive delete uses `${VAR:?}`.
- One sentence says what the line does, what it changes, and what to look for in its output.

Full rule, examples, and rationale: [`standards/user-commands-one-line.md`](../standards/user-commands-one-line.md). Read it before handing the user commands to run.

## Enforcement

Enforced by: [`hooks/user-commands-one-line.py`](../hooks/user-commands-one-line.py).

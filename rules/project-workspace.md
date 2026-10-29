# Project Workspace

Every repository keeps the user's working material in a local workspace that is never committed, and the README stays the single source of truth for the project.

- The workspace root is `<repo>/docs/` when the project does not own it, else `<repo>/.work/`. Resolve it with [`hooks/_lib/project_workspace.py`](../hooks/_lib/project_workspace.py); never guess.
- Never create, edit, or delete a file in a project-owned `<repo>/docs/` for workspace purposes.
- Ignore the workspace through `.git/info/exclude` only, never the committed `<repo>/.gitignore`.
- `<root>/PROMPT.md` must always be pasteable into a new session to continue; rewrite it before ending any turn that changed the repository.
- A file named `PROMPT.md` must never be versioned, in any repository, at any depth, in any case. Never add, force-add, or commit one; to untrack one already committed, use `git rm --cached`.
- Plans, research, requirements, and ADR drafts for the user's work go under the workspace, never at the repo root.
- The README owns what the project is and how to use it. Workspace files link to it, never copy it, and nothing committed links into the workspace.
- In a repository the user does not own, the README is read and pointed to, never edited for this convention.

Full rule, PROMPT.md template, and rationale: [`standards/project-workspace.md`](../standards/project-workspace.md). Read it before writing PROMPT.md or creating workspace files.

## Enforcement

Enforced by: [`hooks/project-workspace.py`](../hooks/project-workspace.py).

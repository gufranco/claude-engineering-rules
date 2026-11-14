# Machine-Agnostic Output

Everything committed or published reads the same for any person on any machine. Nothing from the machine that wrote it reaches a repository, a commit message, a pull request, an issue, or a release note.

- Never write a home directory path, login name, host name, local folder name, terminal window or session name, live session id, or machine temp path into a tracked file.
- Fixtures, examples, demo recordings and regression cases taken from real data keep the property the test needs, such as a space in a path or a two-word name, and replace every value with a neutral one: `/home/user`, `project`, `octocat`, a seeded faker name, a synthetic UUID.
- Paths in code and generated reports are built at runtime from `$HOME`, the repository root, or a temp dir, and are written relative to the repository.
- Documentation never shows output captured on the author's machine without replacing its paths and names; a default shown in a README is the expression, such as `$HOME/Docker`, never its expansion.
- The owner's name, forge handle and public contact address appear only in authorship: license, copyright and SPDX lines, package author metadata, citation, code owners, funding and conduct files.
- Instructions never assume the author's setup: no synced-folder names, no employer or client names in personal projects, no window layout.
- Before committing, grep the diff for every name seen in the environment during the session.

Full rule, examples, and rationale: [`standards/machine-agnostic.md`](../standards/machine-agnostic.md). Read it before writing a fixture from real data, a demo, or a README that shows command output.

## Enforcement

Enforced by: [`hooks/machine-leak-guard.py`](../hooks/machine-leak-guard.py).

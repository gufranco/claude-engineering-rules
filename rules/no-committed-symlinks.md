# No Committed Symlinks

A repository never tracks a symbolic link. Git records one as mode `120000`, and the commit that would add or change one is blocked.

- Shared source is reached through the build: an include path, a source directory list, or a package, never a link into another directory.
- A file needed in two places is committed once, at the place its consumer reads it, and the consumer is pointed there.
- A file taken from a submodule or another project is committed as its own bytes, with the source commit named in the commit message.
- Removing an existing tracked link is always allowed; a commit that touches a repository holding links removes them.
- A script that generates tracked files never emits a link.
- Out of scope: links a script or test creates at runtime outside the index, such as a PATH shim in a temp directory.

Full rule, examples, and rationale: [`standards/no-committed-symlinks.md`](../standards/no-committed-symlinks.md). Read it before replacing a tracked link.

## Enforcement

Enforced by: [`hooks/symlink-commit-blocker.py`](../hooks/symlink-commit-blocker.py).

## Provenance

Added 2026-10-28, `single-incident`, by direct user instruction: links are not allowed in any repository, and rules, standards and hooks must stop them. Origin: an audit found 671 tracked links across the owner's repositories, 670 of them in one project whose demo generator linked shared sources into every demo, and one theme file in dotfiles linked into a submodule.

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

# No Committed Symlinks

## Scope

Loaded on demand before replacing a tracked symbolic link, before writing a script that generates tracked files, and whenever the symlink-commit-blocker hook blocks a commit.

## Core Rule

A repository never tracks a symbolic link. Git stores a link as mode `120000` whose content is the target path, and every consumer of the repository then depends on that path resolving.

| Where the link breaks | What happens |
|---|---|
| Windows checkout without developer mode | Git writes a plain text file holding the target path; the build reads that text as source |
| `git archive`, release tarballs, zip downloads | The link is stored as a link or flattened inconsistently between tools |
| Tools that do not follow links: some linters, coverage maps, Docker build contexts | The file is skipped or read from the wrong place |
| A reader browsing the tree | Two paths show the same content, and nothing says which one is real |

## Replacements

| The link stood for | Replace it with |
|---|---|
| Shared source compiled into several targets | The build's source list: `SOURCEDIRS`, `VPATH`, an include path, a CMake `target_sources`, a package |
| A shared header | An include directory on the compiler command line |
| One file read by a tool from a fixed path | The file itself, committed at that path, and no second copy |
| A file inside a submodule | The file's bytes, committed, with the submodule commit named in the commit message; drop the submodule when nothing else uses it |
| A generated tree of links | A generator that writes build configuration pointing at the shared directory |

Bad, a generator that links shared code into each demo:

```bash
ln -sf ../../../../shared/audio.c "$demo_dir/arm9/source/audio.c"
```

Good, the demo's Makefile reads the shared directory:

```make
SOURCEDIRS := arm9/source ../../shared
INCLUDEDIRS := arm9/source ../../shared
```

## Removing Existing Links

Deleting a tracked link is always allowed; the hook only blocks a commit that adds a link or changes a path into one. Replace and delete in the same commit so every commit builds.

Find them with:

```bash
git ls-tree -r HEAD | awk '$1 == "120000" { print $4 }'
```

## Out of Scope

A link a script or test creates at runtime and never stages, such as a PATH shim in a temp directory or a fixture that feeds a link to the tool under test, is not a committed link. This rule governs the index only.

## Enforcement

[`hooks/symlink-commit-blocker.py`](../hooks/symlink-commit-blocker.py) runs on every Bash `git commit`. It reads the staged diff for new mode `120000` entries, and also the paths that `git commit -a` or a `git add` in the same command would stage, and blocks when any is a link. Bypass once with `SYMLINK_COMMIT_DISABLE=1` in the parent shell, only for a vendored upstream that must stay byte-identical, after asking the user.

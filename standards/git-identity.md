# Git Author Identity Isolation

## Why this standard exists

Multiple identities are configured for git. The wrong identity authoring a commit on a public repo leaks the other account as a public contributor. Path-based detection (`includeIf "gitdir:..."`) misses repos cloned outside the matched paths. A local `[user]` block in `.git/config` overrides any global resolution. Environment variables like `GIT_AUTHOR_EMAIL` bypass config entirely.

This standard makes identity resolution declarative and consistency enforced. Identity comes from the user's private `~/.gitconfig`, scoped to the repository's remote URL. A hook blocks any operation that would commit, amend, or push under a missing, locally overridden, or placeholder identity.

## The pattern

Three layers, each addressing a different failure mode.

| Layer | Mechanism | What it covers |
|-------|-----------|----------------|
| Declarative | `~/.gitconfig` `includeIf "hasconfig:remote.*.url:<glob>"` | Resolves the right identity automatically when entering a repo |
| Defensive | `hooks/git-author-guard.py` | Blocks commits, pushes, and config mutations that would use the wrong identity |
| Documentary | This standard | Explains the pattern, the user gitconfig template, and the hook contract |

The hook does not know any real identity. It validates presence, locality, and non-placeholder shape only. Real identities live exclusively in the user's private `~/.gitconfig`.

## Template for `~/.gitconfig`

This is a template. Replace placeholder values (`personal-user`, `work-org`, `alice@example.com`, `bob@example.org`) with real account names and emails before installing.

```ini
[user]
    useConfigOnly = true

[includeIf "hasconfig:remote.*.url:git@github.com:personal-user/**"]
    path = ~/.gitconfig.personal

[includeIf "hasconfig:remote.*.url:https://github.com/personal-user/**"]
    path = ~/.gitconfig.personal

[includeIf "hasconfig:remote.*.url:git@github.com:work-org/**"]
    path = ~/.gitconfig.work

[includeIf "hasconfig:remote.*.url:https://github.com/work-org/**"]
    path = ~/.gitconfig.work
```

`~/.gitconfig.personal`:

```ini
[user]
    name = Alice Personal
    email = alice@example.com
```

`~/.gitconfig.work`:

```ini
[user]
    name = Bob Work
    email = bob@example.org
```

`useConfigOnly = true` makes git refuse to fall back to a guessed identity from the system. Combined with the includeIf blocks, the only way `user.email` resolves is through one of the matched URL patterns. Any repo with a remote that does not match drops into a hard error from git itself, before any commit happens.

## What the hook enforces

`hooks/git-author-guard.py` runs on PreToolUse for Bash commands. It splits triggers into three categories.

| Category | Triggers | Check |
|----------|----------|-------|
| Commit creation | `git commit`, `git commit --amend`, `git cherry-pick`, `git rebase`, `git revert`, `git merge` with custom commit | Effective `user.email` is non-empty. No `[user]` block in the repository's `.git/config`. No inline `GIT_AUTHOR_EMAIL=` or `GIT_COMMITTER_EMAIL=` |
| Push | `git push`, `git push --force`, `git push --force-with-lease` | Walk `git log --format=%ae @{push}..HEAD`. Block if any author email is empty or matches a placeholder pattern |
| Config mutation | `git config user.email <value>`, `git config user.name <value>`, `git config --local user.*` | Block any `--local` write to `user.*`. Allow `--global` writes (they edit `~/.gitconfig`, the source of truth) |

Read-only commands (`git config --get user.email`, `git status`, `git log`) are not gated.

## Bypass

Set `GIT_AUTHOR_GUARD_DISABLE=1` in the environment to skip every check. Acceptable use cases:

- Anonymizing a fork before publishing.
- Ghostwriting a commit attributed to another author with their consent.
- Tests of the hook itself.

Bypass is auditable: it requires an explicit env var visible on the command line. Never set it as a shell-wide export. Never use it for normal work.

## Detection order

The hook does not pick the identity. The user's `~/.gitconfig` does, through git's native resolution. The hook only verifies the result. If resolution fails, the hook surfaces a message pointing to this standard.

## Adding a new account

1. Create a remote-pattern block in `~/.gitconfig` matching the account's repository URL.
2. Create a small include file (`~/.gitconfig.<name>`) with `[user] name` and `email`.
3. Verify with a fresh repo: `git clone <repo>; cd <repo>; git config --get user.email` returns the expected address.
4. Commit a test change in a sandbox repo to confirm the hook allows it.

## Rules

- Identity resolution lives in `~/.gitconfig`. The hook does not know any real email.
- `useConfigOnly = true` is mandatory. Never let git guess.
- Never set `[user]` in a repository's `.git/config`. Use `~/.gitconfig` includeIf blocks.
- Never inline `GIT_AUTHOR_EMAIL=` or `GIT_COMMITTER_EMAIL=` for normal commits.
- New account? Add the includeIf block before cloning, not after.

## Related standards

- `standards/multi-account-cli.md`: umbrella standard for the multi-account isolation pattern.
- `standards/github-accounts.md`: per-command rules for `gh`.
- `standards/gitlab-accounts.md`: per-command rules for `glab`.
- `standards/hook-authoring.md`: performance budget and exit-code semantics.

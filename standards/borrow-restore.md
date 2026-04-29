# Borrow and Restore

> **First, read `standards/multi-account-cli.md`.** That is the canonical doc for multi-account CLI safety. Borrow-and-restore is a strict fallback for the few tools that have no per-command flag or env var. Most CLIs (`gh`, `glab`, `docker`, `kubectl`, `aws`, `gcloud`, `terraform` workspace, `helm`) support per-command forms and never need this pattern.

## The Pattern

When a tool maintains global mutable state and **has no per-command alternative**, follow this sequence:

1. **Read** the current state. Record it.
2. **Switch** to the required state.
3. **Work.** Do whatever you need to do.
4. **Restore** the original state. Always. Even if step 3 fails.

This is the CLI equivalent of a `try/finally` block. The restore step is not optional.

## When to Apply

Apply this pattern only when the tool has no per-command flag or env var. If the tool supports per-command context (the majority do), use that instead. See `standards/multi-account-cli.md` for the full list of CLIs that have per-command forms.

## Tools That Need Borrow-and-Restore

No CLI in the user's current toolchain requires this pattern. Every tool the user runs supports either a per-command form (see `standards/multi-account-cli.md`) or per-project config files that resolve on every invocation without global mutation.

Specifically:

- Runtime version managers: the user runs `mise`. mise resolves the active version from project config (`.mise.toml`, `.tool-versions`, `.nvmrc`, `.node-version`, `.python-version`, `.ruby-version`, `.terraform-version`) on every shell entry and every `mise exec` call. There is no shared global "active version" that another terminal can change. Older managers like `nvm`, `rvm`, and `pyenv` do mutate a shell-global active version, but they are not in use here.
- Multi-account CLIs (`gh`, `glab`, `docker`, `kubectl`, `aws`, `gcloud`, `terraform` workspace, `helm`): all use per-command forms. See `standards/multi-account-cli.md`.

Borrow-and-restore stays in the toolbox only for the rare case of a future CLI that has neither a per-command flag, an env var, nor a project config file. If you find such a tool, document it here before using the pattern.

## How to Detect the Correct Context

For account and context detection, follow the order in `standards/multi-account-cli.md` (env var, project config, git remote, ask). The same order applies when borrow-and-restore is the only option.

For runtime versions under mise, prefer `.mise.toml` and `.tool-versions` for new projects. mise still reads `.nvmrc`, `.node-version`, `.python-version`, `.ruby-version`, and `.terraform-version` for compatibility with legacy projects, so existing files do not need migration. Run `mise current` to see what mise resolved for the working directory.

## Rules

- **Always restore.** The restore step runs on success and on failure. No exceptions.
- **Never restore to a state you didn't read.** Always record the original state before switching. Restoring to a hardcoded or assumed default is wrong.
- **Restore exactly once.** At the end of the operation, not in the middle, not multiple times.
- **Announce the switch.** When switching context, tell the user what you switched from and to. Silent switches are confusing.
- **Skip if unnecessary.** If the current context already matches the required one, do not switch and do not restore. No-op is always safe.
- **Do not switch if you cannot determine the target.** If there's no signal (env var, config file, convention) telling you which context to use, work with whatever is currently active. Guessing is worse than asking.

## Podman

Podman is daemonless and does not use Docker contexts. Each Podman command targets the local Podman socket directly.

- Verify Podman is installed: `which podman`.
- Use `podman` as a drop-in replacement for `docker` on commands that do not require Compose. For Compose, use `podman-compose` or `docker compose` with `DOCKER_HOST` pointed at the Podman socket.
- When both Docker and Podman are installed, prefer the one the user's project already uses. Check for `docker-compose.yml` (Docker) vs Podman socket in `.envrc`.
- Podman runs as a non-root user by default. Do not prepend `sudo`. If a command requires elevated privileges, ask the user before proceeding.

## Terraform Backend Switching

Never change the active Terraform backend globally. Different projects use different backends (local, S3, GCS, Terraform Cloud) and different workspaces.

- Always run Terraform commands from the correct working directory where `terraform.tf` or `backend.tf` declares the backend.
- Never run `terraform init -reconfigure` without asking. Reconfiguring migrates state, which can cause data loss if the wrong backend is targeted.
- For workspace selection, use `TF_WORKSPACE=<name> terraform ...` per command. See `standards/multi-account-cli.md`. Never run `terraform workspace select` directly.
- Each project environment (dev, staging, production) must have its own workspace or separate state file. Never run production plans from a dev workspace.

## Related Standards

- `standards/multi-account-cli.md`: Per-command CLI safety, the canonical doc for multi-account isolation.
- `standards/infrastructure.md`: Infrastructure.

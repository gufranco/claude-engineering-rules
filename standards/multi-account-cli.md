# Multi-Account CLI Safety

## Why this standard exists

Many CLIs maintain a single global "active account" or "active context" that persists across every terminal on the machine. Switching it in one terminal silently affects every other terminal. Parallel sessions targeting different accounts break.

This standard makes the rule absolute: never switch global state. Detect the account the project expects, fetch its credentials, and inject them per command.

## Coverage

These CLIs are covered. Each has a per-command form that bypasses global state, and each has a hook that hard-blocks the global-mutation command.

| CLI | Per-command form | Anti-pattern command (blocked) | Enforcing hook |
|-----|------------------|-------------------------------|----------------|
| `gh` | `GH_TOKEN=<token> gh ...` | `gh auth switch` | `hooks/gh-token-guard.py` |
| `glab` | `GITLAB_TOKEN=<token> GITLAB_HOST=<host> glab ...` | `glab auth login` | `hooks/glab-token-guard.py` |
| `docker` | `docker --context <name> ...` or `DOCKER_CONTEXT=<name>` env or `DOCKER_HOST=<socket>` env | `docker context use <name>` | `hooks/docker-context-guard.py` |
| `kubectl` | `kubectl --context <name> ...` or `KUBECONFIG=<path>` env | `kubectl config use-context <name>`, `kubectx <name>` | `hooks/kubectl-context-guard.py` |
| `aws` | `aws --profile <name> ...` or `AWS_PROFILE=<name>` env | `aws configure set ...` without `--profile` | `hooks/aws-profile-guard.py` |
| `gcloud` | `gcloud --account=<account> --project=<project> ...` or `--configuration=<name>` flag | `gcloud config set account`, `gcloud config set project`, `gcloud config configurations activate` | `hooks/gcloud-config-guard.py` |
| `terraform` workspace | `TF_WORKSPACE=<name> terraform ...` env | `terraform workspace select <name>` | `hooks/terraform-workspace-guard.py` |
| `mise` | Project-local `.mise.toml` / `.tool-versions`, `mise exec <tool>@<version> -- ...`, `mise x <tool>@<version> -- ...` | `mise use --global <tool>@<version>`, `mise use -g <tool>@<version>` | `hooks/mise-global-guard.py` |
| `helm` | `helm --kube-context <name> ...` | `kubectl config use-context` upstream | covered transitively via `kubectl-context-guard.py` |

Niche CLIs not covered yet (vercel, netlify, fly, az, doctl, heroku, firebase, supabase) follow the same principle: prefer per-command tokens or flags. Add a hook when the user starts running them multi-account.

## Detection order

The agent picks the target account using these signals, in priority order. Stop at the first match.

1. **Explicit env var.** Project's `.env`, `.env.local`, or `.envrc` defines `GH_TOKEN`, `GITLAB_TOKEN`, `DOCKER_CONTEXT`, `KUBECONFIG`, `AWS_PROFILE`, `CLOUDSDK_ACTIVE_CONFIG_NAME`, `TF_WORKSPACE`. Trust it.
2. **Project config file.** Tool-specific files: `.terraform/environment` for workspace, `.kube/config` referenced by KUBECONFIG, `aws-vault` config files, etc.
3. **Git remote inference.** `git remote get-url origin` maps to a known account by host or path. For `gh`, the owner segment of the GitHub URL identifies the account. For `glab`, the host identifies the GitLab instance.
4. **Ask the user.** If no signal exists, ask which account to use. Never guess.

## Per-command forms in detail

### `gh`

```
GH_TOKEN=$(gh auth token --user <login>) gh repo create <login>/<repo> --private
```

`gh auth token --user <login>` reads the stored credential without changing the active account. Loop scripts: export `GH_TOKEN` once at the top.

### `glab`

```
GITLAB_TOKEN=<token> GITLAB_HOST=<host> glab mr list
```

Both env vars are mandatory. `GITLAB_HOST` defaults to `gitlab.com` only when set explicitly; do not rely on the default.

### `docker`

```
docker --context colima-projectA ps
docker --context colima-projectA compose up -d
```

Or set `DOCKER_CONTEXT` once for the script:

```
export DOCKER_CONTEXT=colima-projectA
docker compose up -d
```

For Colima specifically, the context name is `colima` for the default profile and `colima-<profile>` for named profiles. Verify the target Colima profile is running with `colima list` before sending commands.

### `kubectl`

```
kubectl --context prod-cluster get pods
KUBECONFIG=~/.kube/config-prod kubectl get pods
```

`kubectl --context` is the safer form: it does not require swapping kubeconfig files.

### `aws`

```
aws --profile company-prod s3 ls
AWS_PROFILE=company-prod aws s3 ls
```

The hook only blocks `aws configure set` without `--profile`, because that command writes to the default profile. Bare `aws s3 ls` is allowed; it uses whatever profile is currently active and is read-only. The agent should still set `--profile` or `AWS_PROFILE` for clarity when the project expects a specific profile.

### `gcloud`

```
gcloud --account=user@example.com --project=my-project compute instances list
gcloud --configuration=my-config compute instances list
```

`--configuration=<name>` selects a stored gcloud configuration without activating it. Use this when multiple configurations exist.

### `terraform`

```
TF_WORKSPACE=staging terraform plan
TF_WORKSPACE=staging terraform apply
```

`TF_WORKSPACE` overrides the active workspace per command. Some Terraform versions ignore it for certain backends; verify with `terraform workspace show` after running a plan.

### `mise`

```
mise install
mise current
mise exec <tool>@<version> -- <command>
mise x <tool>@<version> -- <command>
mise use <tool>@<version>       # writes to .mise.toml in cwd, project-local
```

mise resolves the active tool version from project config (`.mise.toml`, `.tool-versions`, `.nvmrc`, `.node-version`, `.python-version`, `.ruby-version`, `.terraform-version`) on every invocation. There is no shared "active version" that another terminal can change. `mise use --global` is the only command that writes to the shared `~/.config/mise/config.toml`; the hook blocks it. Pin runtimes per project with `.mise.toml` instead.

### `helm`

```
helm --kube-context prod-cluster list
```

`helm` reads the same kubeconfig as `kubectl`. The `--kube-context` flag mirrors `kubectl --context`.

## Anti-pattern commands

Every command in this table is blocked by a hook. The fix is always to use the per-command form above.

| Command | Why it breaks parallel terminals |
|---------|----------------------------------|
| `gh auth switch --user <login>` | Mutates the active GitHub account in shared config |
| `glab auth login` | Rewrites global glab config including host and token |
| `docker context use <name>` | Mutates active Docker context for every shell |
| `kubectl config use-context <name>` | Mutates active Kubernetes context globally |
| `kubectx <name>` (with arg) | Wrapper that calls `kubectl config use-context` |
| `aws configure set ...` (no `--profile`) | Mutates the default AWS profile in `~/.aws/config` |
| `gcloud config set account <value>` | Mutates active gcloud account globally |
| `gcloud config set project <value>` | Mutates active gcloud project globally |
| `gcloud config configurations activate <name>` | Switches active configuration globally |
| `terraform workspace select <name>` | Writes the active workspace into local Terraform state |
| `mise use --global <tool>@<version>` | Writes to `~/.config/mise/config.toml`, the global fallback every shell reads |
| `mise use -g <tool>@<version>` | Short form of the above, same effect |

## Adding a new CLI

When the user starts running a new CLI multi-account, add coverage in five steps.

1. **Verify the per-command form.** Read the CLI's help: `<cli> --help`, `<cli> auth --help`, `<cli> config --help`. Confirm a flag (`--profile`, `--context`) or env var works without mutating global state.
2. **Identify the anti-pattern command.** The one that mutates the active account or context globally.
3. **Write `hooks/<cli>-<context>-guard.py`** following the gh-token-guard template. Stdin JSON parse, regex match, allow read-only and per-command forms, hard-block the anti-pattern, exit 2 with a pointer to this standard.
4. **Add fixtures** under `tests/fixtures/`: at minimum one blocked scenario and one allowed scenario, ideally also a read-only and a no-op fixture.
5. **Wire the hook** in `settings.json` under `PreToolUse > Bash`. Update the coverage table in this file. Update `rules/security.md` Hook Coverage table.

## Rules summary

- Never run any command in the anti-pattern table. Hooks block them.
- Always use the per-command form. The hook allows it.
- Detect the account from env, then config, then git remote, then ask.
- When in doubt, ask the user. Guessing the account is worse than asking.
- New multi-account CLI? Add a hook before running it more than once.

## Related standards

- `standards/github-accounts.md`: detailed per-command rules for `gh`.
- `standards/gitlab-accounts.md`: detailed per-command rules for `glab`.
- `standards/borrow-restore.md`: fallback pattern for tools without a per-command form.
- `standards/hook-authoring.md`: performance budget and exit-code semantics for new hooks.

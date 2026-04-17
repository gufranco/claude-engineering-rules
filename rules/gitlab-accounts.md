# GitLab Multi-Account Safety

Never rely on the global `glab` config. Never call `glab auth login` during a session.

## Account Detection

Before running any `glab` command:

1. Determine the target instance and account. Check git remote: `git remote get-url origin 2>/dev/null`, or use what the user specifies.
2. Prefix every `glab` command with `GITLAB_TOKEN` and `GITLAB_HOST` inline.

```bash
# Correct: token and host scoped to this command only
GITLAB_TOKEN=glpat-xxx GITLAB_HOST=gitlab.com glab mr list

# Wrong: relies on global config that another terminal can change
glab mr list
```

## Account Mapping

| Remote URL pattern | Host | How to get token |
|---|---|---|
| `gitlab.com` | `gitlab.com` | From config or user |
| Self-hosted instance | The instance hostname | From config or user |
| No remote or ambiguous | Ask the user | Ask the user |

## Rules

- Every `glab` invocation must have `GITLAB_TOKEN=` and `GITLAB_HOST=` prefixed. No exceptions.
- Never run `glab auth login` during a session. It mutates global config shared across all terminals.
- When running multiple `glab` commands in a loop, set both variables once with `export` at the top of the script.
- If the instance or account cannot be inferred from the remote URL or user instructions, ask before proceeding.

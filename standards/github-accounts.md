# GitHub Multi-Account Safety

Multiple GitHub accounts are configured. The `gh` CLI uses a global active account that any terminal can change at any time. Never rely on `gh auth switch`. Never call `gh auth switch`.

## Account Detection

Before running any `gh` command:

1. Determine the target account. Check git remote: `git remote get-url origin 2>/dev/null`, or use the account the user specifies.
2. Prefix every `gh` command with the account's token inline.

```bash
# Correct: token scoped to this command only
GH_TOKEN=$(gh auth token --user gufranco) gh repo create gufranco/my-repo --private

# Wrong: changes global state, breaks other terminals
gh auth switch --user gufranco
gh repo create gufranco/my-repo --private
```

## Account Mapping

| Remote URL pattern | Account |
|---|---|
| `gufranco` | `gufranco` |
| `gfranco-onyxodds` or `onyxodds` | `gfranco-onyxodds` |
| No remote or ambiguous | Ask the user |

## Rules

- Every `gh` invocation must have `GH_TOKEN=` prefixed. No exceptions.
- Never run `gh auth switch`. It mutates global state shared across all terminals.
- When running multiple `gh` commands in a loop, set `GH_TOKEN` once with `export` at the top of the script, not per command.
- If the account cannot be inferred from the remote URL or user instructions, ask before proceeding.

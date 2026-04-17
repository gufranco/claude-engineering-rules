# GitHub Multi-Account Safety

Multiple GitHub accounts are configured. The `gh` CLI uses a global active account that any terminal can change at any time. Never rely on `gh auth switch`. Never call `gh auth switch`.

## Account Detection

Before running any `gh` command:

1. Determine the target account. Check git remote: `git remote get-url origin 2>/dev/null`, or use the account the user specifies.
2. Prefix every `gh` command with the account's token inline.

```bash
# Correct: token scoped to this command only
GH_TOKEN=$(gh auth token --user <account>) gh repo create <account>/my-repo --private

# Wrong: changes global state, breaks other terminals
gh auth switch --user <account>
gh repo create <account>/my-repo --private
```

## Account Mapping

Infer the account from the git remote URL. If the remote is ambiguous or absent, ask the user which account to use.

| Remote URL pattern | Account |
|---|---|
| Matches personal remote | Personal account |
| Matches work/org remote | Work account |
| No remote or ambiguous | Ask the user |

## Rules

- Every `gh` invocation must have `GH_TOKEN=` prefixed. No exceptions.
- Never run `gh auth switch`. It mutates global state shared across all terminals.
- When running multiple `gh` commands in a loop, set `GH_TOKEN` once with `export` at the top of the script, not per command.
- If the account cannot be inferred from the remote URL or user instructions, ask before proceeding.

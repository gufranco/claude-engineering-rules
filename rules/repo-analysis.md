# Repository Analysis

## Core Rule

When you need to read, search, or analyze code from a repository that is not already on disk, clone it to a temporary directory and work against the local checkout. Never fetch individual files through the GitHub or GitLab API one at a time.

API-based file fetching is slow, token-expensive, rate-limited, and produces partial views. A single shallow clone gives full repo context for the same cost as 3-5 API file reads.

## Mandatory Workflow

```bash
WORKDIR=$(mktemp -d -t repo-analysis-XXXXXX)
git clone --depth=1 <repo-url> "$WORKDIR/repo"
cd "$WORKDIR/repo"
# now use Read, Grep, Glob freely
```

When history is needed for the analysis (blame, log, prior versions), drop `--depth=1` or run `git fetch --unshallow` afterwards.

When the target is a single branch other than the default: `git clone --depth=1 --branch <name> --single-branch <repo-url> "$WORKDIR/repo"`.

Authenticate per [`standards/multi-account-cli.md`](../standards/multi-account-cli.md) when the repo is private. For GitHub: `git clone https://x-access-token:$(gh auth token --user <account>)@github.com/<owner>/<repo>.git`.

## Forbidden Patterns

| Pattern | Why it is banned |
|---------|------------------|
| `gh api repos/<o>/<r>/contents/<path>` to read source files | One HTTP round-trip per file. Slow, rate-limited, content is base64 wrapped |
| `gh repo view <o>/<r> --json ...` to enumerate files | Returns metadata, not content. Leads to per-file API calls |
| `curl https://raw.githubusercontent.com/.../<path>` in a loop | Same problem, no auth caching, no grep across the result set |
| Asking an Explore or general-purpose agent to "read files from `<owner>/<repo>` via gh" | Pushes the anti-pattern down into a subagent where it compounds |
| Reading 3+ files from the same remote repo through any HTTP API | The break-even point is around two files. At three, clone |

## Carve-Outs

The rule covers source-file content. Other GitHub or GitLab operations are unaffected:

| Operation | Use |
|-----------|-----|
| Listing or filtering issues, PRs, runs | `gh issue list`, `gh pr list`, `gh run list` |
| Reading a PR diff for review | `gh pr diff <n>` is one call and returns the full diff |
| Code search across many repos at once | `gh search code` is the right tool for cross-repo grep |
| Reading a single README to decide whether to clone | `gh api repos/<o>/<r>/readme` is acceptable as a pre-clone probe |
| Inspecting workflow files in CI failure triage | The repo is already cloned in the CI workspace; analyze there |

The cutoff is "am I about to read more than two source files from the same remote repo?" If yes, clone.

## Cleanup

The temporary directory is the orchestrator's responsibility. Either:

- Use `mktemp -d` under `$TMPDIR` and rely on OS cleanup, acceptable for short sessions.
- Track the path and run `rm -rf "$WORKDIR"` when the analysis is complete.

Never clone into the user's working repo, into `~/.claude/`, or into any path that a hook or git operation might mistake for project source. The `repo-analysis-` prefix on the temp directory makes the intent visible to any audit.

## Briefing Subagents

When delegating repo analysis to an Explore, general-purpose, or research agent, the prompt must include:

- The target repo URL.
- A pre-cloned local path, when the orchestrator has already cloned, so the agent does not re-clone.
- The explicit instruction: "Do not use `gh api .../contents`, `gh repo view`, or raw.githubusercontent.com to read source files. The repo is at `<path>`; use Read, Grep, Glob against that path."

A subagent that fetches files through the API is a wasted run. Discard the response and re-brief.

## Mechanical Enforcement

The hook [`../hooks/repo-fetch-blocker.py`](../hooks/repo-fetch-blocker.py) blocks `gh api .../contents/<path>`, `gh repo view <o>/<r> <path>`, `glab api .../repository/files/<path>`, and `curl`/`wget` against `raw.githubusercontent.com` (plus the GitLab and Bitbucket raw equivalents) at PreToolUse on Bash. Bypass: `REPO_FETCH_DISABLE=1` exported in the parent shell.

## Cross-References

- [`pre-flight.md`](pre-flight.md) "Duplicate Check" step 5 names `gh search code` as a cross-repo grep tool, which remains correct and is not in conflict with this rule.
- [`../standards/multi-account-cli.md`](../standards/multi-account-cli.md) for the authentication pattern when the target repo is private.
- [`../CLAUDE.md`](../CLAUDE.md) "External Tools" section is the cross-tooling baseline this rule extends.

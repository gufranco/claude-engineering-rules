# Repository Analysis

To read code from a repository not on disk, clone it to a temp directory and work locally.

- `git clone --depth=1 <url> "$(mktemp -d -t repo-analysis-XXXXXX)/repo"`; drop `--depth=1` when history matters.
- Never read source through `gh api .../contents`, `gh repo view`, or `raw.githubusercontent.com`. At three files from one repo, clone.
- Allowed: `gh pr diff`, `gh issue list`, `gh search code`, one README probe.
- Never clone into the working repo or the config repo.
- Subagent briefs name the cloned path and forbid API fetching.
- Bypass `REPO_FETCH_DISABLE=1` from a parent shell.

Full rule and rationale: [`standards/repo-analysis.md`](../standards/repo-analysis.md). Read it before analyzing a private or remote repository.

# Pre-Flight

No implementation without pre-flight verification. Skip only for single-line fixes, typos, and obvious config tweaks.

- Duplicate check, stop at first match: local `rg`, open PRs, branches via `git branch -a --list`, closed PRs, `gh search code`, library docs with `llms.txt` first, package registry, web search last
- Before a new skill or agent, search the existing skills, agents, and on-demand index entries; extend over creating
- Feature planning: run `/research` across competitors, open source, and the user's repos before designing; features in 3+ sources are market-validated
- Reference projects inform ideas, never technology choices; prefer the existing stack
- Follow-up requirements merge into the existing plan, never replace it
- Architecture fit: read surrounding code; rules win over local patterns
- Verify every interface touched: signatures, routes, schemas, env vars. A threshold copied from existing code must match quantity, action, conditions, and population
- Bug fixes: reproduce and explain why before writing the fix
- Record the warning baseline on files you will change; the count after must not rise
- State files that change and the boundary that does not; ask one question if scope is unclear

Full rule, examples, and rationale: [`standards/pre-flight.md`](../standards/pre-flight.md). Read it before planning a feature, running market research, or reusing a threshold from existing code.

## Enforcement

Enforced by: [`hooks/scope-guard.py`](../hooks/scope-guard.py).

# AI Bot Triage

Reference for `/respond` when `--include-bots` is set. The skill defers AI bot threads to `/ship --pipeline` by default. This file documents the per-tool false-positive catalog, the command grammar for the major reviewers, and the teach-once playbook.

## Severity Baseline

Treat every AI-bot comment as P3 until corroborated by a human reviewer or by a verification check. Independent audits, as of 2026-05, show:

| Tool | Precision | False-positive rate | Catch rate |
|------|-----------|---------------------|------------|
| CodeRabbit | ~50% | Moderate, especially on style | High on common patterns |
| Greptile | Variable | Highest in the cohort | Highest catch rate |
| Copilot review | 71% actionable | Lower than CodeRabbit | High on security and obvious bugs |
| Cursor BugBot | Variable | Moderate | High on runtime defects |
| Sourcery | Lower precision on small repos | Moderate | Best for refactors |
| Qodo Merge | Variable | Lower than CodeRabbit | High on test gaps |
| Korbit | Limited public data | Limited public data | Limited public data |

Source: independent benchmarks from `greptile.com/benchmarks`, `devtoolsacademy.com/blog/state-of-ai-code-review-tools-2025/`, and the May 2026 GitHub Blog post on Copilot review metrics.

## False-Positive Catalog

### Style and convention violations

| Pattern | Why the bot is wrong | How to dismiss |
|---------|---------------------|----------------|
| Suggests Prettier or ESLint changes that contradict the project's config | The bot does not always read the local config | "Project lint config is the source of truth. See `.eslintrc.json`. Resolving." |
| Suggests adding JSDoc to a TypeScript file | Project convention may be types-as-docs | "Project convention is types-as-docs. JSDoc is reserved for public APIs. Resolving." |
| Suggests renaming for consistency with a different file | The other file may itself be the outlier | "The pattern in this file is consistent with `src/services/*Service.ts`. Resolving." |
| Suggests removing what looks like a `console.log` but is actually a structured logger call | Pattern matching against `console.` without reading the import | "The `console.log` is actually `logger.log` aliased at the top of the file. Resolving." |

### Imagined APIs

| Pattern | Why the bot is wrong | How to dismiss |
|---------|---------------------|----------------|
| Suggests `lodash.debounce` in a project that bans lodash | The bot does not check `package.json` or dependency policy | "Project bans `lodash`. Internal helper at `src/utils/debounce.ts`. Resolving." |
| Suggests a method that does not exist on the chosen library | Hallucinated API surface | "Method not in `<library>` API. See `node_modules/<library>/types/index.d.ts`. Resolving." |
| Suggests a flag that does not exist on the CLI being invoked | Same root cause | "Flag does not exist in this version of `<tool>`. Resolving." |

### Defensive programming overreach

| Pattern | Why the bot is wrong | How to dismiss |
|---------|---------------------|----------------|
| "Add a try/catch" on code that intentionally propagates the error | The bot does not see the call-site contract | "Error propagates intentionally to the DLQ at `src/consumers/orderConsumer.ts:42`. Resolving." |
| "Add a null check" on a value that is typed non-null | The bot does not always trust the type system | "Type-system-enforced non-null at the boundary. See `src/types/order.ts`. Resolving." |
| "Validate the input" on input that is already validated upstream | The bot reads the function in isolation | "Validated at the API boundary in `src/middleware/validate.ts:30`. Resolving." |
| Suggests `array.length > 0` check before `array.forEach` | `.forEach` is a no-op on empty arrays | "`forEach` is a no-op on empty arrays. No-op guard adds noise. Resolving." |

### Security false positives

| Pattern | Why the bot is wrong | How to dismiss |
|---------|---------------------|----------------|
| Flags `Math.random()` for cryptographic use when the use is not cryptographic | Pattern matching without context | "Used for random animation jitter, not for security. Crypto is in `src/security/`. Resolving." |
| Flags a hardcoded string as a secret when it is a public configuration value | Bot does not classify the value | "Public config, not a secret. Documented at `docs/config.md`. Resolving." |
| Flags a SQL string concatenation that is actually using a query builder | Pattern matching against `${`, missing the builder wrapper | "Uses the query builder, not raw SQL. See the imports. Resolving." |

### Architecture and refactoring overreach

| Pattern | Why the bot is wrong | How to dismiss |
|---------|---------------------|----------------|
| Suggests extracting a 3-line block into a helper | Below the cost-benefit threshold | "Three similar lines is better than a premature abstraction. Resolving." |
| Suggests inverting a dependency that has a single consumer | DI overhead with no benefit | "Single consumer; DI would add indirection with no test or swap benefit. Resolving." |
| Suggests splitting a 60-line file into multiple files | File length is not the right axis | "File length is fine for the cohesion level. Resolving." |
| Suggests switching from sync to async without measuring | The async path may be slower in practice | "Profile: sync path is 0.8ms, async would be 1.4ms minimum. Resolving." |

### Performance false positives

| Pattern | Why the bot is wrong | How to dismiss |
|---------|---------------------|----------------|
| Flags `for...of` and suggests `.forEach` for "performance" | Both compile to similar bytecode; `.forEach` is not faster | "No measurable difference. Resolving." |
| Suggests memoization for a function called once | Memoization has setup cost | "Called once per request. Memoization would not help. Resolving." |
| Suggests using `Map` instead of `Object` for "performance" | Object access is fine when keys are static | "Static keys, no perf benefit from `Map`. Resolving." |
| Suggests `Array.prototype.flat` over manual iteration | Both work; flat may be slower for shallow cases | "Manual iteration is fine; depth is always 1. Resolving." |

### Test false positives

| Pattern | Why the bot is wrong | How to dismiss |
|---------|---------------------|----------------|
| "Add a test for this private function" | Project policy may forbid direct private-function tests | "Private function tested through the public API at `tests/orders.spec.ts:42`. Resolving." |
| "Test edge case X" when X is impossible by type | The bot does not check the type constraints | "Type makes X unreachable. Resolving." |
| "Mock the database" on integration tests | Project policy bans mocking internal infrastructure | "Integration tests hit a real database by policy. See `tests/setup.ts`. Resolving." |

## Teach-Once Playbook

When the bot is wrong, reply with a one-line educational dismissal that names the project rule the bot missed. The pattern:

```
<short reason>. <reference to the rule or file>. Resolving.
```

Examples:

1. "Project ban on `lodash`. See `CONTRIBUTING.md`. Resolving."
2. "Already validated upstream in `src/middleware/validate.ts:42`. Resolving."
3. "Convention is types-as-docs. See `CONTRIBUTING.md` section 4.2. Resolving."

CodeRabbit and similar tools learn from dismissals over 2 to 4 weeks. The reply must:

- Be short. One sentence plus the resolving signal.
- Name the project rule that the bot missed.
- Be public. The reviewer scrolling the PR should see the same reason the bot does.

## Command Grammar

### CodeRabbit

| Command | Effect |
|---------|--------|
| `@coderabbitai review` | Single re-pass on the current SHA |
| `@coderabbitai full review` | Full deep re-pass |
| `@coderabbitai resolve` | Bulk-resolve all CodeRabbit threads. Use only after addressing each one |
| `@coderabbitai ignore` in PR body | Disable CodeRabbit on this PR |
| `@coderabbitai pause` in PR body | Pause re-review during heavy iteration |
| `@coderabbitai resume` | Resume |
| `@coderabbitai summary` | Print a summary of the PR's changes |
| `@coderabbitai generate sequence diagram` | Generate a Mermaid sequence diagram from the diff |
| `@coderabbitai configuration` | Show the current CodeRabbit config |
| `@coderabbitai help` | Print the command grammar |

Notes:

- The `resolve` command violates the "no bulk resolve" rule in `/respond`. Do not use it through `/respond`. If the user wants bulk resolution outside the skill, the `bulk-resolve-blocker.py` hook should be bypassed explicitly.
- The Agentic Chat feature lets the author reply inline asking for explanation, test generation, or doc addition. `/respond` does not invoke Agentic Chat; it treats CodeRabbit threads as standard threads.

### Cursor BugBot

| Command | Effect |
|---------|--------|
| `bugbot run` (top-level comment) | Trigger a new BugBot pass |
| `cursor review` (top-level comment) | Same |

Notes:

- BugBot does not support conversational replies as of May 2026. The reply to a BugBot comment is visible to humans but not to BugBot.
- Triggering BugBot via the commands creates new threads. Address them in the next `/respond` invocation.

### GitHub Copilot Code Review

As of May 2026:

| Action | UI |
|--------|----|
| "Fix with Copilot" | Per-comment button. Opens a dialog to apply directly or open a new PR |
| "Fix batch with Copilot" | On the PR Overview comment. Hand off multiple comments to the Copilot cloud agent |
| Dismiss | Per-comment dismiss button |

Notes:

- Replies to Copilot review comments are visible to humans but not to Copilot. Copilot does not read its own thread history.
- Severity labels of High, Medium, and Low ship with each Copilot comment. Use the severity to prioritize triage.

### Greptile, Sourcery, Korbit, Qodo Merge

Author command grammars are not publicly documented for these tools. Treat them as standard threads with reply via REST and resolve via GraphQL. Address each in `/respond` using the regular workflow.

### Cursor BugBot on the IDE Side

The Cursor IDE offers a separate review workflow that runs locally. When the user is in Cursor, the IDE may surface BugBot suggestions before they reach the PR. `/respond` only handles PR-side bot comments, not IDE-side suggestions.

## Per-Tool Strategy Summary

| Tool | Default strategy in /respond |
|------|------------------------------|
| CodeRabbit | Skip by default. With `--include-bots`, triage with the teach-once playbook |
| Greptile | Skip by default. With `--include-bots`, expect higher false-positive rate; verify each finding before implementing |
| Copilot | Skip by default. With `--include-bots`, trust High severity, scrutinize Medium and Low |
| Cursor BugBot | Skip by default. With `--include-bots`, treat as standard threads; do not reply expecting BugBot to respond |
| Sourcery | Skip by default. With `--include-bots`, focus on refactor suggestions; dismiss style if it contradicts the project lint config |
| Qodo Merge | Skip by default. With `--include-bots`, focus on test gap findings |
| Korbit | Skip by default. With `--include-bots`, treat as standard threads |
| `dependabot[bot]`, `renovate[bot]`, `github-actions[bot]` | Always skip. These are not review bots; they are dependency or CI bots. Handled by `/ship --pipeline` or by manual `gh` workflow |

## Never Credit a Bot

Never add a commit author or co-author trailer that names any AI tool. The personal CLAUDE.md rule forbids this, and the `ai-attribution-blocker.py` hook enforces it at runtime. When the bot's catch was good, the credit goes to the human who triaged the bot's comment, not to the bot.

## Source Notes

CodeRabbit command grammar from `docs.coderabbit.ai/guides/commands`. Cursor BugBot trigger commands from `cursor.com/bugbot` and the May 2026 forum thread. Copilot UI behavior from the May 2026 GitHub Blog post. Benchmark numbers from `greptile.com/benchmarks` and `devtoolsacademy.com/blog/state-of-ai-code-review-tools-2025/`. The false-positive catalog draws on practitioner reports from `coderabbit.ai/blog/code-review-best-practices-for-vibe-coding`, the Sourcery documentation, and discussions on `news.ycombinator.com` and `lobste.rs`. Patterns are independently described.

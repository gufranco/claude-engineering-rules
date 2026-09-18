# AI Bot Triage

Reference for `/respond` when `--include-bots` is set. AI bot threads are handed to `/ship --pipeline` by default. This file documents the per-tool false-positive catalog and the command grammar for the major reviewers.

**A bot thread receives no reply.** Read it, apply the failure-scenario gate, fix what survives, resolve the thread. [`../../rules/pr-comment-discipline.md`](../../rules/pr-comment-discipline.md) is the rule, and the "How to dismiss" column below is a note to yourself about why the finding fails, never text to publish.

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

## False-Positive Catalog

### Style and convention violations

| Pattern | Why the bot is wrong | Why the finding fails |
|---------|---------------------|-----------------------|
| Suggests Prettier or ESLint changes that contradict the project's config | The bot does not always read the local config | Project lint config is the source of truth. See `.eslintrc.json`. |
| Suggests adding JSDoc to a TypeScript file | Project convention may be types-as-docs | Project convention is types-as-docs. |
| Suggests renaming for consistency with a different file | The other file may itself be the outlier | The pattern in this file is consistent with `src/services/*Service.ts`. |
| Suggests removing what looks like a `console.log` but is actually a structured logger call | Pattern matching against `console.` without reading the import | The `console.log` is actually `logger.log` aliased at the top of the file. |

### Imagined APIs

| Pattern | Why the bot is wrong | Why the finding fails |
|---------|---------------------|-----------------------|
| Suggests `lodash.debounce` in a project that bans lodash | The bot does not check `package.json` or dependency policy | Project bans `lodash`. Internal helper at `src/utils/debounce.ts`. |
| Suggests a method that does not exist on the chosen library | Hallucinated API surface | Method not in `<library>` API. See `node_modules/<library>/types/index.d.ts`. |
| Suggests a flag that does not exist on the CLI being invoked | Same root cause | Flag does not exist in this version of `<tool>`. |

### Defensive programming overreach

| Pattern | Why the bot is wrong | Why the finding fails |
|---------|---------------------|-----------------------|
| "Add a try/catch" on code that intentionally propagates the error | The bot does not see the call-site contract | Error propagates intentionally to the DLQ at `src/consumers/orderConsumer.ts:42`. |
| "Add a null check" on a value that is typed non-null | The bot does not always trust the type system | Type-system-enforced non-null at the boundary. See `src/types/order.ts`. |
| "Validate the input" on input that is already validated upstream | The bot reads the function in isolation | Validated at the API boundary in `src/middleware/validate.ts:30`. |
| Suggests `array.length > 0` check before `array.forEach` | `.forEach` is a no-op on empty arrays | `forEach` is a no-op on empty arrays. No-op guard adds noise. |

### Security false positives

| Pattern | Why the bot is wrong | Why the finding fails |
|---------|---------------------|-----------------------|
| Flags `Math.random()` for cryptographic use when the use is not cryptographic | Pattern matching without context | Used for random animation jitter, not for security. Crypto is in `src/security/`. |
| Flags a hardcoded string as a secret when it is a public configuration value | Bot does not classify the value | Public config, not a secret. Documented at `docs/config.md`. |
| Flags a SQL string concatenation that is actually using a query builder | Pattern matching against `${`, missing the builder wrapper | Uses the query builder, not raw SQL. See the imports. |

### Architecture and refactoring overreach

| Pattern | Why the bot is wrong | Why the finding fails |
|---------|---------------------|-----------------------|
| Suggests extracting a 3-line block into a helper | Below the cost-benefit threshold | Three similar lines is better than a premature abstraction. |
| Suggests inverting a dependency that has a single consumer | DI overhead with no benefit | Single consumer; DI would add indirection with no test or swap benefit. |
| Suggests splitting a 60-line file into multiple files | File length is not the right axis | File length is fine for the cohesion level. |
| Suggests switching from sync to async without measuring | The async path may be slower in practice | Profile: sync path is 0.8ms, async would be 1.4ms minimum. |

### Performance false positives

| Pattern | Why the bot is wrong | Why the finding fails |
|---------|---------------------|-----------------------|
| Flags `for...of` and suggests `.forEach` for "performance" | Both compile to similar bytecode; `.forEach` is not faster | No measurable difference. |
| Suggests memoization for a function called once | Memoization has setup cost | Called once per request. Memoization would not help. |
| Suggests using `Map` instead of `Object` for "performance" | Object access is fine when keys are static | Static keys, no perf benefit from `Map`. |
| Suggests `Array.prototype.flat` over manual iteration | Both work; flat may be slower for shallow cases | Manual iteration is fine; depth is always 1. |

### Test false positives

| Pattern | Why the bot is wrong | Why the finding fails |
|---------|---------------------|-----------------------|
| Add a test for this private function | Project policy may forbid direct private-function tests | Private function tested through the public API at `tests/orders.spec.ts:42`. |
| "Test edge case X" when X is impossible by type | The bot does not check the type constraints | Type makes X unreachable. |
| "Mock the database" on integration tests | Project policy bans mocking internal infrastructure | Integration tests hit a real database by policy. See `tests/setup.ts`. |

## A Wrong Finding Is Closed, Never Answered

Resolve the thread. Write nothing into it.

Some vendors claim their tool learns from a written dismissal over two to four weeks. The claim is unverified here, and it was the only argument that ever favored writing to a bot. Against the cost, a reply on every false positive, on every pull request, for a reader that does not exist, the trade is not worth taking.

When a bot misses the same project rule repeatedly, the durable fix is the tool's own configuration file: a CodeRabbit `.coderabbit.yaml` path filter, a lint config the tool respects, an instructions file the vendor reads. That survives; a comment does not.

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
- Agentic Chat would have the author reply inline asking for explanation or test generation. `/respond` never invokes it. A question asked of a bot is a comment published for no reader.

### Cursor BugBot

| Command | Effect |
|---------|--------|
| `bugbot run` | Trigger a new BugBot pass |
| `cursor review` | Same |

Notes:

- Both commands are published as a pull-request comment, which is banned. Trigger a fresh pass by pushing a commit, or ask the user to run the command themselves when a re-pass is genuinely needed.
- BugBot does not support conversational replies as of May 2026, so a reply reaches humans only. Under the reply-only rule there is no reply to consider.

### GitHub Copilot Code Review

As of May 2026:

| Action | UI |
|--------|----|
| Fix with Copilot | Per-comment button. Opens a dialog to apply directly or open a new PR |
| Fix batch with Copilot | On the PR Overview comment. Hand off multiple comments to the Copilot cloud agent |
| Dismiss | Per-comment dismiss button |

Notes:

- Copilot does not read its own thread history, so a reply would reach humans only. There is no reply either way.
- Severity labels of High, Medium, and Low ship with each Copilot comment. Use the severity to prioritize triage.

### Greptile, Sourcery, Korbit, Qodo Merge

Author command grammars are not publicly documented for these tools. Treat them as standard bot threads: verify, fix what holds, resolve via GraphQL, publish nothing.

### Cursor BugBot on the IDE Side

The Cursor IDE offers a separate review workflow that runs locally. When the user is in Cursor, the IDE may surface BugBot suggestions before they reach the PR. `/respond` only handles PR-side bot comments, not IDE-side suggestions.

## Per-Tool Strategy Summary

| Tool | Default strategy in /respond |
|------|------------------------------|
| CodeRabbit | Skip by default. With `--include-bots`, verify each finding, fix what holds, resolve the rest |
| Greptile | Skip by default. With `--include-bots`, expect higher false-positive rate; verify each finding before implementing |
| Copilot | Skip by default. With `--include-bots`, trust High severity, scrutinize Medium and Low |
| Cursor BugBot | Skip by default. With `--include-bots`, verify and resolve. No reply, to BugBot or to the thread |
| Sourcery | Skip by default. With `--include-bots`, focus on refactor suggestions; resolve style findings that contradict the project lint config |
| Qodo Merge | Skip by default. With `--include-bots`, focus on test gap findings |
| Korbit | Skip by default. With `--include-bots`, treat as standard threads |
| `dependabot[bot]`, `renovate[bot]`, `github-actions[bot]` | Always skip. These are not review bots; they are dependency or CI bots. Handled by `/ship --pipeline` or by manual `gh` workflow |

## Never Credit a Bot

Never add a commit author or co-author trailer that names any AI tool. The personal CLAUDE.md rule forbids this, and the `ai-attribution-blocker.py` hook enforces it at runtime. When the bot's catch was good, the credit goes to the human who triaged the bot's comment, not to the bot.

---
name: second-opinion
description: Cross-model code review using an alternative AI model for independent perspective. Uses Ollama (local), OpenAI, or other configured providers. Three modes: gate (pass/fail), adversarial (break the code), consult (open discussion). Use when user says "second opinion", "cross-model review", "independent review", "another model", "double check with another AI", or wants verification from a different model. Do NOT use for standard code review (use /review), security audit (use /audit), or design review (use /review design).
---

Send code to an alternative AI model for independent review. Catches single-model blind spots by getting a second perspective from a fundamentally different system.

The value is not in any specific model. It is in the independence of the perspective. Two models agreeing on an issue is a strong signal. Two models missing the same issue is a gap worth noting.

## Arguments

- No arguments: review the current branch diff in gate mode.
- File path(s) or PR number: review specific files or a PR.
- `--mode gate`: pass/fail decision with blocking issues listed (default).
- `--mode adversarial`: actively try to break the code. Find edge cases, race conditions, security holes.
- `--mode consult`: open-ended discussion about design decisions and trade-offs.
- `--provider <name>`: force a specific provider (ollama, openai). Default: auto-detect.

## Provider Detection

Check for available providers in this order:

1. **Ollama (local, preferred).** Check if Ollama MCP server is configured in `settings.json` or run `which ollama`. No API key required. No data leaves the machine.
2. **OpenAI.** Check for `OPENAI_API_KEY` in environment. If available, use the chat completions API.
3. **Other providers.** Check for any other LLM MCP server configured in `settings.json`.

If no alternative model is available, stop and tell the user how to set one up:
- Ollama: `brew install ollama && ollama pull llama3.1`
- OpenAI: set `OPENAI_API_KEY` in the environment

## Process

### Gate Mode (default)

1. **Collect the diff.** Run `git diff` for local changes, or `gh pr diff <number>` for a PR.

2. **Build the review prompt.** Send to the alternative model:

   ```
   Review this code diff for issues. Focus on:
   - Correctness: logic errors, off-by-one, null handling, edge cases
   - Security: injection, auth bypass, data exposure, SSRF
   - Performance: unnecessary allocations, O(n^2), missing indexes
   - Concurrency: race conditions, missing await, shared state

   For each issue found, state:
   - File and line number
   - What the issue is
   - Why it matters
   - Suggested fix

   If no issues found, state "PASS" with a brief rationale.

   Diff:
   <diff content>
   ```

3. **Collect findings.** Parse the alternative model's response.

4. **Cross-reference.** Run the same review with Claude (the primary model) if not already done. Compare:

   | Finding | Alternative model | Claude | Confidence |
   |---------|------------------|--------|------------|
   | ... | Found | Found | High (both agree) |
   | ... | Found | Not found | Investigate |
   | ... | Not found | Found | Investigate |

5. **Report:**

   ```
   ## Second Opinion: Gate Review

   **Provider:** <model name and version>
   **Files reviewed:** <count>
   **Verdict:** PASS / FAIL

   ### Findings (alternative model)
   <numbered list of issues>

   ### Cross-Reference
   **Overlapping:** <issues both models found>
   **Unique to <model>:** <issues only the alternative found>
   **Unique to Claude:** <issues only Claude found>

   ### Recommendation
   <MERGE / FIX REQUIRED / DISCUSS>
   ```

### Adversarial Mode

Same as gate mode, but the prompt changes to:

```
You are a hostile code reviewer. Your job is to break this code.

For each attack vector:
- Describe the attack scenario
- Show the specific input or sequence that triggers it
- Rate the severity (critical / high / medium / low)
- Suggest a fix

Consider: injection, auth bypass, race conditions, resource exhaustion,
edge cases in business logic, type confusion, encoding attacks,
timing attacks, state corruption.

Diff:
<diff content>
```

### Consult Mode

Interactive session where the diff is sent with an open-ended prompt:

```
Review this code and share your thoughts on:
- Architecture and design decisions
- Alternative approaches worth considering
- Long-term maintainability concerns
- Testing strategy gaps

Be opinionated. If you would do something differently, say so and explain why.

Diff:
<diff content>
```

Present the response to the user as-is, prefixed with the model name, so the user can evaluate both perspectives.

## Rules

- Ollama (local) is the preferred provider. No data leaves the machine. No API costs.
- Never send secrets, credentials, or `.env` file contents to external APIs. Strip them from the diff before sending.
- The alternative model's output is a second opinion, not authority. Present findings for the user to evaluate.
- Two models agreeing is a strong signal but not proof. The user always decides.
- Two models disagreeing on the same issue is the most valuable outcome: it highlights genuine ambiguity.
- Rate limit awareness: if using an external API, batch the review into a single request. Do not send line-by-line.
- If the alternative model is unavailable or returns an error, report the failure and suggest the user run `/review` instead. Do not silently skip the second opinion.

## Related skills

- `/review` -- Primary code review with 52-category checklist.
- `/audit` -- Security-focused audit with vulnerability scanning.
- `/review qa` -- QA analysis for test coverage gaps.

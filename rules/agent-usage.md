# Agent and Parallelism Budget

## Core Rule

Default to inline work. Spawn agents only when the task cannot be done with direct tool calls.

## Decision Gate

Before calling the Agent tool:

1. Can I do this with 2-4 direct Glob, Grep, Read, or Bash calls? If yes, do that instead
2. Is the work truly independent of the current context? If I need the result before I can continue, spawn in the foreground. If genuinely decoupled, spawn in the background
3. How many agents am I about to spawn in one message? More than two parallel agents is almost always wrong

## Rate Budget Awareness

- Spawning N agents in parallel is N× the rate pressure in the same window
- If the count is 3 or more, stop and reconsider. Can any be replaced with a direct tool call? Can any be sequenced?
- If the user explicitly requested parallel execution, proceed, but note the rate cost

## When Agents Are Justified

| Situation | Justified? |
|-----------|-----------|
| Exploring an unfamiliar codebase with 10+ unknown files | Yes, Explore agent |
| Finding a single file or function by name | No, use Glob or Grep |
| Running a multi-step research task that would consume the main context | Yes, general-purpose agent |
| Reading 2-3 files in parallel | No, use parallel Read calls directly |
| Running tests or builds and waiting for output | No, use Bash |
| Implementing code changes in an isolated branch | Yes, worktree isolation |
| Checking CI status while doing other work | Only if genuinely non-blocking |

## Parallelism Rule

Use parallel **tool calls** (multiple tools in one message) freely for independent reads, searches, and lookups.

Use parallel **Agent launches** sparingly. At most two concurrent agents. Never three or more unless the user explicitly requested it.

## Sequencing Over Parallelism

Prefer: finish A, use A's results for B.
Avoid: launch A, B, and C simultaneously to save time, then stall when rate limit triggers.

## Token Cost Anatomy

Every agent spawn consumes three token pools: the orchestrator's full accumulated context, the subagent initialization prompt, and the subagent's response. Three concurrent agents use 3-5× the tokens of inline work. The further into a session, the more expensive each spawn becomes.

## Context Amnesia

Subagents start with a blank slate. Without explicit injection, a subagent will re-read already-processed files, contradict decisions already made, and inflate the orchestrator's context.

**What to inject into every agent prompt:**
- Specific file paths relevant to the task. Paths only, not contents
- Decisions already made that the agent must respect
- The exact output format expected: bullet list, JSON schema, or file:line pairs
- **Test requirements.** Every agent that writes production code must write or update tests to maintain 95%+ coverage. State this explicitly: "Write tests for all new methods. Target 95%+ coverage."
- **Quality gate commands.** Include the exact commands the agent must run before declaring done: typecheck, lint, format

**What to never inject:**
- Raw contents of large files. Send the path and let the agent read if needed
- Full conversation history or prior tool output dumps
- Vague instructions like "review the codebase" with no scope boundary

## Custom Agents (`.claude/agents/`)

A custom agent is a markdown file with frontmatter: `name`, `description`, a `tools` list, and an optional `model` field. Use for recurring specialized tasks (security reviews, migration planning, test generation). Use the general-purpose Agent tool for one-off research and context-window-protection tasks.

## Cascade Prevention

**Rule: agents must not spawn further agents.** One level of delegation only.

When writing an agent prompt, add: "Do not spawn subagents. Complete this task using direct tool calls only."

Exception: if multi-level orchestration is genuinely needed, state it explicitly in the delegation prompt.

## Stop Signals

Stop a running agent and redo inline when:

1. **Re-reading known files.** The agent is reading files you already read in the main session. Context injection was insufficient
2. **Output contradicts a prior decision.** The blank-slate problem occurred. The result cannot be used without reconciliation

## Result Size Management

Every agent prompt must specify the output format explicitly.

Good prompt: "Review `src/auth/`. Return: a bullet list of issues, each as `file:line: description`. Maximum 10 items. No prose."

Never ask an agent to return raw file contents, full function bodies, or explanatory prose. If the agent needs to share code, ask for file paths and line ranges only.

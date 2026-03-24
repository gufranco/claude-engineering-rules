# Agent and Parallelism Budget

## Core Rule

Default to inline work. Spawn agents only when the task cannot be done with direct tool calls.

## Decision Gate

Before calling the Agent tool, answer these questions:

1. Can I do this with 2-4 direct Glob, Grep, Read, or Bash calls? If yes, do that instead.
2. Is the work truly independent of the current context? If I need the result before I can continue, spawn in the foreground. If the work is genuinely decoupled, spawn in the background.
3. How many agents am I about to spawn in one message? More than two parallel agents is almost always wrong. Each concurrent agent hits the same rate limit window simultaneously.

If any answer points toward doing the work inline, do it inline.

## Rate Budget Awareness

Spawning N agents in parallel is N× the rate pressure in the same window. Before spawning multiple agents concurrently:

- Count how many agents you plan to launch.
- If the count is 3 or more, stop and reconsider. Can any of them be replaced with a direct tool call? Can any be sequenced instead of parallelized?
- If the user explicitly requested parallel execution, proceed, but note the rate cost.

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

Use parallel **tool calls** (multiple tools in one message) freely for independent reads, searches, and lookups. This has near-zero overhead.

Use parallel **Agent launches** sparingly. At most two concurrent agents. Never three or more in one message unless the user explicitly requested it.

## Sequencing Over Parallelism

When in doubt, sequence. A sequential approach that takes 10% longer is always better than a parallel approach that saturates the rate window, forces a pause, and blocks the rest of the session.

Prefer: finish A, use A's results for B.
Avoid: launch A, B, and C simultaneously to save time, then stall when rate limit triggers.

## Token Cost Anatomy

Every agent spawn consumes three token pools at once: the orchestrator's full accumulated context, the subagent initialization prompt, and the subagent's response returning to the orchestrator. None of these is small.

A moderately complex task spawning 3 concurrent agents uses roughly 50-150K tokens per session: 3-5× what doing the same work inline would cost. The orchestrator context alone is the largest variable. The further into a session, the more expensive each spawn becomes.

This is why the two-agent cap and sequencing rules exist. The overhead is not the agent's work. It is the context duplication across N simultaneous windows.

## Context Amnesia

Subagents start with a blank slate. They do not inherit the main session's memory, decisions, or in-progress context.

Without explicit injection, a subagent will re-read files already processed, contradict decisions already made, and return results that inflate the orchestrator's context further when they arrive.

**What to inject into every agent prompt:**
- The specific files or paths relevant to the task, not their contents. Paths only.
- Decisions already made that the agent must respect
- The exact output format expected: bullet list, JSON schema, or file:line pairs

**What to never inject:**
- Raw contents of large files. Send the path and let the agent read if needed.
- Full conversation history or prior tool output dumps
- Vague instructions like "review the codebase" with no scope boundary

## Custom Agents (`.claude/agents/`)

The general-purpose Agent tool is for one-off delegation. For recurring specialized tasks, define a custom subagent file in `~/.claude/agents/` for global scope or `.claude/agents/` for project scope.

A custom agent is a markdown file with frontmatter: `name`, `description`, a `tools` list scoped to what the agent needs, and an optional `model` field. Claude matches tasks to custom agents by description at delegation time.

Use custom agents for: security reviews, migration planning, API design checks, test generation for a specific framework. These tasks recur, benefit from a consistent system prompt, and should not consume the full general-purpose agent tool budget.

Use the general-purpose Agent tool for: one-off deep research, context-window-protection tasks, and worktree isolation jobs that don't fit a standing pattern.

## Cascade Prevention

The highest-risk failure mode: an agent that spawns further agents. A general-purpose agent given a broad, unscoped task will parallelize internally, compounding the rate pressure exponentially.

**Rule: agents must not spawn further agents.** One level of delegation only.

The escape hatch: if the task genuinely requires multi-level orchestration and quality would suffer without it, that override is valid. It must be stated explicitly in the delegation prompt: "this task requires sub-delegation to X and Y agents." If it is not stated, the agent must do the work inline.

When writing an agent prompt, add: "Do not spawn subagents. Complete this task using direct tool calls only."

## Stop Signals

A running agent that shows either of these signals should be stopped and redone inline:

1. **Re-reading known files.** If the agent's tool calls show it reading files you already read in the main session, it is duplicating work. The context injection was insufficient. Stop, add the missing context, and retry. Or redo it inline.
2. **Output that contradicts a prior decision.** If the agent returns a result that conflicts with a decision already made in the session, the blank-slate problem occurred. The result cannot be used without reconciliation, which costs more context than starting over.

To abort: stop the agent, note what context was missing, add it to the prompt, and re-evaluate whether spawning is still the right approach.

## Result Size Management

Agent output re-enters the main context in full. A verbose agent response inflates the session and accelerates rate exhaustion.

Every agent prompt must specify the output format explicitly. Require the minimum structure needed to act on the result.

Bad prompt: "Review the authentication module and tell me what you find."
Good prompt: "Review `src/auth/`. Return: a bullet list of issues, each as `file:line: description`. Maximum 10 items. No prose."

Never ask an agent to return raw file contents, full function bodies, or long explanatory prose. If the agent needs to share code, ask for file paths and line ranges only. Read the relevant lines inline after the agent finishes.

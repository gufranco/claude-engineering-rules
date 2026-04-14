# Cost Awareness

## Token Cost of Agent Spawning

Every agent spawn duplicates the orchestrator's accumulated context. The further into a session, the more expensive each spawn becomes.

| Agents spawned | Estimated token cost | Equivalent inline cost |
|---------------|---------------------|----------------------|
| 1 agent | 15-50K tokens | 5-15K tokens |
| 2 concurrent agents | 30-100K tokens | 10-30K tokens |
| 3 concurrent agents | 50-150K tokens | 15-45K tokens |

The overhead is not the agent's work. It is the context duplication across simultaneous windows. Three agents cost 3-5x what doing the same work inline would cost.

## Model Selection for Subtasks

Match the model to the task complexity. Not every operation needs the most capable model.

| Task type | Preferred model tier | Justification |
|-----------|---------------------|---------------|
| Read-only analysis, file search | Haiku | Low token cost, sufficient capability |
| Code generation, refactoring | Sonnet | Balance of quality and cost |
| Architecture decisions, complex debugging | Opus | Highest capability needed |

When spawning agents, specify the model explicitly if the task is read-only or simple.

## Avoiding Redundant File Reads

Every file read consumes context tokens. Read strategically.

| Pattern | Cost | Fix |
|---------|------|-----|
| Reading the same file twice in one session | 2x tokens | Read once, reference by line numbers |
| Reading an entire 2000-line file for one function | Thousands of wasted tokens | Use offset and limit parameters |
| Agent re-reads files the orchestrator already read | Full duplication | Send file paths to agent, let it read only if needed |
| Reading a file to check if it exists | Unnecessary tokens | Use Glob or ls instead |

## Agent Output Size Control

Agent output re-enters the main context in full. Verbose responses inflate the session.

Every agent prompt must specify the output format:

```
# Bad: open-ended
"Review the auth module and tell me what you find."

# Good: bounded
"Review src/auth/. Return a bullet list of issues, each as
file:line: description. Maximum 10 items. No prose."
```

## CI Pipeline Cost

Every `git push` triggers a full CI pipeline run. Pipeline runs consume paid runner minutes.

| Practice | Cost impact |
|----------|------------|
| Push after every commit | N pipeline runs for N commits |
| Push once after all local gates pass | 1 pipeline run |
| Fix CI failures one at a time, push each fix | N pipeline runs for N fixes |
| Batch all CI fixes, push once | 1 pipeline run |

Rules:
- Accumulate local commits. Push once at the end of the task.
- When CI fails with multiple issues, fix all locally before pushing.
- One push with all fixes, not one push per fix.

## Rate Budget and Sequencing

Parallel agent spawns hit the same rate limit window simultaneously. When the rate budget is tight:

- Sequence over parallelize. A sequential approach that takes 10% longer is better than a parallel approach that triggers a rate limit pause.
- Before spawning multiple agents, count how many you plan to launch. Three or more is almost always wrong.
- Replace simple agent tasks with direct tool calls: Glob, Grep, Read, Bash.

## Cost-Aware Decision Tree

Before any operation, ask:

1. Can I do this with a direct tool call instead of an agent? If yes, do that.
2. Can I read just the relevant section instead of the whole file? If yes, use offset and limit.
3. Can I batch these operations into fewer pushes? If yes, batch them.
4. Is the model tier appropriate for this task's complexity? If not, adjust.
5. Have I specified the output format to prevent verbose agent responses? If not, add constraints.

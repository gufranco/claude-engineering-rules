# AI Vocabulary

Canonical glossary for AI coding terminology. Use these definitions in PRs, ADRs, retros, and rule files. Avoid synonym drift across the codebase. Inspired by Matt Pocock's dictionary of AI coding.

## When to consult

- Writing a PR description, ADR, or retro that touches AI tooling behavior.
- Naming a failure mode in an incident report.
- Defining acceptance criteria for an agent-driven workflow.

## The Model

| Term | Plain definition |
|------|------------------|
| Token | Unit the model reads and writes. Roughly word-sized but not equal to a word. Pricing and context limits are token-based |
| Parameters | The model's learned weights. Frozen at training time. Not the same as runtime configuration |
| Inference | One forward pass that produces output. Each call is an inference |
| Request | One API call to the model. May contain many turns of history |
| Non-determinism | Same input can produce different outputs across runs. Temperature and sampling cause this |
| Parametric knowledge | What the model learned during training. Cannot be updated without retraining |
| Contextual knowledge | What the model sees in the current request. Resets when the context window evicts it |

## Sessions, Context, Turns

| Term | Plain definition |
|------|------------------|
| Context window | The maximum number of tokens the model can attend to in a single request |
| Turn | One user message plus one assistant response. A session is a sequence of turns |
| Session | The full conversation thread. May span many turns and many requests |
| Compaction | Summarizing earlier turns to free context window space. Lossy by nature |
| Cache hit | Reusing the prompt prefix from a previous request. Reduces cost and latency |
| Attention degradation | Quality drop when the context window fills. Models pay less attention to middle content |

## Tools and Environment

| Term | Plain definition |
|------|------------------|
| Tool | A function the model can call. Has a name, schema, and side effects |
| Tool call | A single invocation of a tool by the model |
| Tool result | The structured output returned to the model from a tool call |
| Allowlist | Explicit set of tools or commands the agent may use. Default-deny everything else |
| Sandbox | An environment that constrains what the agent can read, write, or execute |
| Workspace | The filesystem and shell the agent operates against in a session |

## Failure Modes

| Term | Plain definition |
|------|------------------|
| Hallucination | The model produces plausible content that is factually wrong. File paths, function names, API methods that look correct but do not exist |
| Sycophancy | The model agrees with the user even when the user is wrong. Caused by RLHF reward signals |
| Plausible drift | Generated code looks right line by line but does not solve the actual problem |
| Optimistic error handling | Catches that log without classifying, recovering, or propagating |
| Invented API | A method signature that fits the library's style but does not match its real surface |

## Handoffs

| Term | Plain definition |
|------|------------------|
| Handoff | A structured note that lets a fresh session resume work without replaying the prior session |
| Context snapshot | A frozen record of task, constraints, files touched, and decisions at a point in time |
| Resume signal | An explicit instruction in a handoff that tells the next session where to start |

## Memory and Steering

| Term | Plain definition |
|------|------------------|
| Memory | Cross-session persistence. File-based notes the assistant reads on future runs |
| Supersede chain | A memory update pattern that preserves the previous version via frontmatter pointers instead of overwriting |
| Steering | Durable guidance that shapes behavior across sessions. Rules, standards, instructions |
| Skill | A named, scoped procedure the assistant can execute. Has frontmatter, optional supporting files, and tool allowlist |

## Patterns of Work

| Term | Plain definition |
|------|------------------|
| Human in the loop | Workflow that requires explicit user approval at defined gates |
| AFK run | Long-running autonomous execution without human supervision. Higher risk, requires safety rails |
| Automated review | A pass that critiques output before a human sees it. Often a second model with adversarial framing |
| Self-review loop | The agent reads its own diff and applies a checklist before declaring done |

## Rules

- Use the canonical term. Do not introduce synonyms without superseding the existing entry.
- When a new failure mode appears, add it here before referencing it elsewhere.
- Cross-reference: tie each term to the rule or standard that operationalizes it where one exists.

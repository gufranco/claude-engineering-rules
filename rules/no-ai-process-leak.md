# No AI Process Leak

## Core Rule

Any text another engineer will read must read as if a human engineer wrote it. Never expose the workflow shape that produced the change. Specifically: do not name phases, plans, spec folders, canvas regions, ADR numbers, or workflow milestones in commit messages, pull-request descriptions, release notes, code comments, or chat messages destined for other humans.

This rule is enforced mechanically by `~/.claude/hooks/ai-process-leak-blocker.py`. A blocked tool call means the rule was violated. The bypass `AI_PROCESS_LEAK_DISABLE=1` exists only for the rare case of editing the planning artifacts themselves.

## Why This Rule Exists

Earlier sessions produced commits with subjects and bodies like:

```
chore(repo): bootstrap regnant project scaffolding

Initial Phase 0 of the regnant plan. Lays down the meta files needed
before any real code...

Refs: specs/2026-05-22-atlassian-platform-terraform/plan.md
```

The user flagged this immediately: no human writes "Phase 0 of the plan" or "Refs: specs/<date>-<slug>/plan.md" in a commit. These phrases publish that the change came out of an AI-driven multi-phase plan. They are subtler than `Co-authored-by: Claude` but just as identifying.

The narrow `ai-attribution-blocker.py` hook misses them because it scans only explicit attribution strings. The narrow `internal-config-leakage.py` hook misses them because it scans `~/.claude/` paths, not project-level planning paths. This rule and its companion hook fill the gap.

## In Scope

The rule applies to every artifact a human reader can see outside the planning folder:

- `git commit -m` subject and body
- `git tag -m`, `git notes` add/append
- `gh pr create`, `gh pr edit`, `gh pr review`, `gh release create`, `gh issue create/edit/comment`
- `glab mr create/update`, `glab release create`
- Code comments, doc-string preambles, README files outside docs/adr and project planning folders
- Slack messages, email drafts, status updates written by the assistant
- CHANGELOG entries

It does not apply inside the planning folder itself. Files under project `specs` trees, `docs/adr/`, `docs/plan*`, `docs/runbook*`, and the entire `~/.claude/` tree may legitimately contain phase-N language, plan references, canvas-region mappings, and the like. The hook skip-list covers these paths.

## Forbidden Patterns

| Pattern | Why it leaks |
|---------|--------------|
| `Phase 0`, `Phase 1`, `Phase 12` | Multi-phase plan is an AI artifact. Humans group commits by feature, not by phase number |
| `of the plan`, `per the plan`, `the regnant plan` | References the planning document as authority |
| `Refs:` followed by a planning path | Plan path inside the repo |
| The literal string plan-dot-md anywhere in commit text | Same |
| `spec folder`, `spec folders` | Generated-by-AI workflow vocabulary |
| `Maps to canvas region N`, `canvas region` | Design-artifact mapping language |
| `ADR-0001`, `ADR-0012` referenced casually | ADRs are fine as docs; mentioning them by number in commits reads as cross-linking by an LLM |
| `state-of-the-art`, `state of the art` | Hyperbole tell. Humans use specific quality claims, not category superlatives |
| `100% faithful`, `fully faithful`, `absolutely faithful` | Faithfulness language is process self-congratulation |
| `lands in phase N`, `comes online in phase N` | Phase-relative scheduling |
| `following the plan`, `as the plan describes` | Plan-as-authority language |

This list is the hook's regex set. It is not exhaustive. The principle stands: if a sentence describes the process of generating the change, it does not belong outside the planning folder.

## How To Write A Commit Or PR Description Instead

A commit message answers two questions: what changed, and why. Nothing more.

Bad:

```
chore(repo): bootstrap regnant project scaffolding

Initial Phase 0 of the regnant plan. Lays down the meta files needed
before any real code: license, contributor guides, lint config,
Conventional Commits, dependency automation, codeowners, and the
Makefile orchestrator.

This commit intentionally ships no infrastructure, services, or tests.
Phase 1 (Docker Compose foundation) starts in the next commit.

Refs: a planning path
```

Good:

```
chore: initial project scaffolding

Apache 2.0 license, CODEOWNERS, SECURITY.md, CONTRIBUTING.md, the
Makefile, pre-commit config, Renovate, Dependabot, and the standard
editorconfig / gitattributes / gitignore set.
```

The good version is shorter, names what changed, and contains no AI-process tells. A reader cannot tell whether a human or an AI produced it.

## How To Write A Code Comment Instead

Code comments describe the code. They never describe how the code was produced.

Bad:

```python
# Implementation deferred to Phase 11.
# See the planning document, task 96.
```

Good:

```python
# TODO: implement the worker idempotency path before the first
# real provisioning request lands.
```

The good version uses the standard `TODO:` convention any reader recognizes, names the concrete future work, and contains no plan reference.

## Self-Test Before Committing Or Posting

For every commit message, PR description, code comment, or chat message destined for another human, ask:

1. Does any sentence describe the process that produced this change?
2. Does any sentence reference a plan, spec, phase, or canvas?
3. Does any sentence contain hyperbole I would not say out loud to a teammate?
4. Could a reader tell, from this text alone, that an AI assisted?

If any answer is yes, rewrite before sending. The hook will block the worst of it; this self-test catches the rest.

## Bypass

The bypass `AI_PROCESS_LEAK_DISABLE=1` is for editing planning artifacts that legitimately contain phase-N language and spec paths. Examples: project planning docs, ADRs, the rule files in `~/.claude/`. Export the variable in the parent shell before invoking Claude Code on those files. Never set it inline on a single command, because the hook reads the command string before the assignment takes effect.

## Cross-References

- `~/.claude/CLAUDE.md` "No AI attribution" covers the narrower explicit-attribution case.
- `~/.claude/rules/git-workflow.md` "Commit Format" defines the subject and body envelope.
- `~/.claude/rules/writing-precision.md` covers the broader precision floor.
- `~/.claude/standards/code-review.md` "No Internal Config Leakage" covers the related class of `~/.claude/` path leaks (different hook).
- `~/.claude/hooks/ai-process-leak-blocker.py` is the enforcement layer.

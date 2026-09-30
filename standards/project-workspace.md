# Project Workspace

## Core Rule

Every repository the user works in has three things:

1. A README that is the single source of truth for what the project is, how to install it, and how to use it.
2. A local workspace folder holding what the user's work needed: research, requirements, plans, decision drafts, notes. It is never committed, and its contents serve the user's work rather than the project.
3. `PROMPT.md` in that workspace, current enough to paste into a fresh session and continue with no other context.

The workspace never touches files the project owns.

## Why This Rule Exists

The convention first appeared in `fd3206-write-unlock`, where one session set up a gitignored `<repo>/docs/` with a continuation prompt, and every later session resumed from it without re-explaining anything. Other repositories had no such folder, and continuation prompts ended up scattered in whatever directory the session happened to be in.

A rule alone did not spread the convention, for the same timing reason described in [`doc-truth.md`](doc-truth.md): a prompt goes stale at the end of a turn that changed code, and a rule loaded at session start does not fire then. Enforcement therefore sits at three moments:

| Moment | Mechanism |
|---|---|
| Session start | [`hooks/project-workspace.py`](../hooks/project-workspace.py) claims the folder in `.git/info/exclude`; [`hooks/session-resume-context.py`](../hooks/session-resume-context.py) names it and injects `PROMPT.md` |
| End of a turn that changed the repository | [`hooks/project-workspace.py`](../hooks/project-workspace.py) blocks the stop once while `PROMPT.md` is older than the newest change |
| Staging | [`hooks/project-workspace.py`](../hooks/project-workspace.py) refuses `git add --force` over the workspace |

Work repositories often track their own `<repo>/docs/`. On 2026-09-30, `company-brain` tracked 85 files there, `eevee` 75, `onyx_fullstack` 20. The user's constraint: a workspace must never interfere with a project's own documentation.

## Workspace Root

[`hooks/_lib/project_workspace.py`](../hooks/_lib/project_workspace.py) resolves the root. Never pick it by hand.

| Repository state | Root |
|---|---|
| `<repo>/docs/` absent, or an empty directory | `<repo>/docs/` |
| `<repo>/docs/` holds an untracked `PROMPT.md`, or the exclude file carries the managed entry for it | `<repo>/docs/` |
| `<repo>/docs/` has a tracked file, holds content without `PROMPT.md`, or is a file | `<repo>/.work/` |
| `<repo>/.work/` is taken the same way | `<repo>/.work-local/` |

Ownership is sticky. `.git/info/exclude` carries the line `# local workspace, never committed` above each entry the hook wrote, so a workspace that later gains files still resolves to the same folder. When the project starts tracking files under a claimed folder, the next session start removes that claim and falls back.

## Ignore Mechanism

- Always `.git/info/exclude`. It is local, invisible to reviewers, and shared by every worktree of the repository.
- Never add the workspace to the committed `<repo>/.gitignore`. That is a diff in someone else's project.
- An existing committed entry, as in `fd3206-write-unlock`, stays as it is.
- A forced add over the workspace is blocked. A plain add is refused by git itself because the path is excluded.

## Layout

```
<root>/
  PROMPT.md
  plans/<YYYY-MM-DD>-<slug>/plan.md, decisions.md, references.md, context.md
  research.md, requirements.md, development.md, adr/, notes as the work needs them
```

Only `PROMPT.md` is required. `/plan` writes its dated plan folders to `<root>/plans/`. A project that commits living specs under `specs/current/` keeps them there, because those describe the project, not the user's work.

## PROMPT.md

`PROMPT.md` is a prompt, written to be pasted as the first message of a new session. It is overwritten in place on every update. History lives in the project's git log and in the vault, never appended here.

### Required sections

1. **Identity.** The project, its repository, and what it is in one sentence, with a pointer to the README for the rest.
2. **Read first.** The README, the project's agent instruction file, and the workspace files that matter now, in reading order.
3. **Hard constraints.** One line each, only what the user set and the code cannot show.
4. **State as of YYYY-MM-DD.** What is done, what is verified, what is not verified, and anything waiting on someone else.
5. **Next steps.** Numbered, in order, each concrete enough to start without asking.
6. **Decided against.** Options not to re-propose, each with its reason in one clause.

### Template

```markdown
# Prompt to continue in a new session

Paste everything below the line into a new session opened in `<repo path>`.

---

Continue work on <project>, <one sentence>. Repository: <url>. The README is the source of truth for what it does and how to use it.

Read first: `README.md`, `<AGENTS.md or CLAUDE.md>`, `<root>/requirements.md`, `<root>/plans/<current plan>/plan.md`.

Constraints I set:

- <constraint>

State as of <YYYY-MM-DD>: <done, verified, not verified>.

Next steps:

1. <step>

Decided against, do not re-propose unless I raise it: <option, reason>.
```

### Content rules

- Never copy README content; link to the README section instead.
- No secrets. Apply the redaction list from [`skills/checkpoint/SKILL.md`](../skills/checkpoint/SKILL.md).
- Dates are absolute. Never "yesterday" or "last week".
- Write it for a reader with no memory of this session.

## README as Single Source of Truth

- The README owns the description, install, usage, configuration, and commands.
- Every other public copy is derived from it: repository description, package manifest `description`, formula `desc`, release notes, listings.
- Change the README first, then propagate.
- Nothing committed links into the workspace, since those paths do not exist in a clone. [`hooks/ai-process-leak-blocker.py`](../hooks/ai-process-leak-blocker.py) blocks published text naming a workspace `PROMPT.md` or `plans/` path.
- In a repository the user does not own, the README belongs to its maintainers: read it and point to it, and edit it only when the task itself requires a documentation change under [`doc-truth.md`](doc-truth.md).

## Bypass

`PROJECT_WORKSPACE_DISABLE=1` in the parent shell, or the bypass registry entry `project-workspace`. The stop check blocks at most once per stop chain, so a bypass is for a named false positive only.

## Provenance

Promoted 2026-09-30, `single-incident`, by direct user instruction. Origin: the `fd3206-write-unlock` convention of a gitignored workspace with a continuation prompt worked, while continuation prompts elsewhere were scattered across `data-monorepo/planning/` and `internal-tools/apps/arrows/`, and the README-as-source preference had been stated in two projects on 2026-09-22 without any rule carrying it. The `<repo>/.work/` fallback exists because the user stated that other companies' documentation folders must not be touched.

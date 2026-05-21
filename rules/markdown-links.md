# Markdown Link Discipline

## Core Rule

Every file mention in published repo markdown is a clickable link to the actual file when the file exists in the repo. No exceptions in prose. Code blocks and intentional bare-token spans are exempt.

GitHub renders relative paths as file or folder views. A bare backtick reference is friction the reader has to overcome. A linked reference cuts navigation from a search to a click.

## Scope

The rule applies to every `.md` file in the repo root, [`skills/`](../skills/), [`rules/`](../rules/), [`standards/`](../standards/), and [`checklists/`](../checklists/).

The validator at [`scripts/validate-markdown-links.py`](../scripts/validate-markdown-links.py) is advisory for `specs/` files, blocking for everywhere else.

Out of scope for v1: `.mdx`, `.rst`, `.adoc` formats.

## Two Acceptable Forms

```markdown
Plain link form:        [file.ext](file.ext)
Code-styled link form:  [`file.ext`](file.ext)
```

Both render as clickable. The code-styled form uses backticks inside the link text to keep the monospace look for file names.

## Exception Zones

The rule does not apply inside:

- **Fenced code blocks.** Bare paths stay as-is. Compensate with a linked summary line above or below the block.
- **Inline code spans that show a command, shell prompt, or literal output.** Detection signal: the span contains a space, a `$` prompt, or option flags. Commands have spaces; file paths usually do not.
- **Markdown link URLs themselves.** The URL fragment is allowed to be a path.
- **Front-matter blocks** delimited by `---`.
- **HTML comment blocks** delimited by `<!-- -->`.

## Path Resolution

- Paths resolve relative to the document containing the reference.
- Case-sensitive. `Hooks/foo.py` does not resolve to `hooks/foo.py` on a case-sensitive filesystem.
- Directory paths resolve to the directory view. Example: `[`skills/`](skills/)`.
- Files outside the repo are not linkable through relative paths. Use the external URL form.

## Repeat Mentions

When the same file is mentioned multiple times in the same section, link only the first occurrence. Subsequent mentions can be plain code spans without a link, to reduce visual noise.

## Tables

Tables in the README skills and hooks sections always link the file column. Example:

```markdown
| Hook | Trigger |
|------|---------|
| [`dangerous-command-blocker.py`](hooks/dangerous-command-blocker.py) | PreToolUse Bash |
| [`gh-token-guard.py`](hooks/gh-token-guard.py) | PreToolUse Bash |
```

## Validator Integration

[`scripts/validate-markdown-links.py`](../scripts/validate-markdown-links.py) runs on every CI Lint job. It fails the build on any bare file reference that resolves to an existing repo file.

Run locally:

```bash
python3 scripts/validate-markdown-links.py
```

Exit code 1 with line-cited findings on failure. Exit code 0 when clean.

## Hook Integration

[`hooks/markdown-link-discipline.py`](../hooks/markdown-link-discipline.py) runs PreToolUse on Write, Edit, and MultiEdit for `.md` files. The hook is diff-aware: it blocks only when the change introduces a NEW bare reference whose path resolves to a real file. Pre-existing bare references are left alone so legacy markdown can be edited without triggering the hook.

Bypass via `MARKDOWN_LINKS_DISABLE=1`. Export in the parent shell because inline env vars do not reach the hook.

## Skip-List

Directories whose markdown intentionally shows bare-path examples, like test fixtures, validator self-tests, and CI definitions:

- `tests/`
- `scripts/`
- `.github/`
- `tools/`
- `specs/`. Advisory only inside this tree.

Files explicitly exempt by name:

- [`rules/markdown-links.md`](markdown-links.md). This rule file itself, which shows counter-examples.

## Why This Rule Exists

The repo is public-facing. New visitors land on the GitHub repo page and use the README to navigate. Bare backtick references force them to copy the file name into the file finder, search, or `cd`. A linked reference is one click.

The same applies to skill files, standards, and rule files: contributors browsing them benefit from one-click navigation to the files they describe.

The earlier README-only rule in [`skills/readme/SKILL.md`](../skills/readme/SKILL.md) covered the marketing-grade variant only and was not enforced. This file generalizes the rule and pairs it with the validator and hook for enforcement.

## Cross-References

The following skills produce markdown that this rule governs:

- [`skills/readme/SKILL.md`](../skills/readme/SKILL.md)
- [`skills/plan/SKILL.md`](../skills/plan/SKILL.md)
- [`skills/assessment/SKILL.md`](../skills/assessment/SKILL.md)
- [`skills/pr-summary/SKILL.md`](../skills/pr-summary/SKILL.md)
- [`skills/incident/SKILL.md`](../skills/incident/SKILL.md)
- [`skills/onboard/SKILL.md`](../skills/onboard/SKILL.md)
- [`skills/explain/SKILL.md`](../skills/explain/SKILL.md)
- [`skills/retro/SKILL.md`](../skills/retro/SKILL.md)

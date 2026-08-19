# Contributing

Thanks for taking the time. This repository is an opinionated engineering
config, so a change here changes how an agent behaves on someone's machine.
The bar is correspondingly high, and most of it is mechanical.

## TL;DR

Fork, branch, run `make test-all` until it is green, and open a pull request
with a Conventional Commits title. CI runs eight jobs and every one of them
must pass. Releases are automatic: your commit type decides the next version,
so the type is not cosmetic.

## Getting Set Up

```bash
git clone https://github.com/gufranco/claude-engineering-rules.git
cd claude-engineering-rules

python3 -m venv .venv
make install

npm ci --ignore-scripts
```

`make install` reads [`requirements-dev.txt`](requirements-dev.txt), which is
the single source of truth for the Python toolchain. CI installs from the same
file, so a version bump lands in one place and cannot drift between your
machine and the pipeline.

The Node toolchain exists only to run `semantic-release`. You need it if you
touch [`.releaserc.json`](.releaserc.json) or
[`scripts/sync-plugin-versions.mjs`](scripts/sync-plugin-versions.mjs).

## The Local Gate

Run this before every push. It is the same set CI runs, so a green run here is
a green pipeline.

```bash
make test-all
```

That expands to:

| Target | What it does |
|--------|--------------|
| `make test-cov` | pytest with branch coverage, gated at 95% |
| `make test-bats` | bats-core suites for the shell hooks |
| `make lint` | ruff, shellcheck, actionlint, yamllint |
| `make typecheck` | mypy --strict |

Run `make format` before `make lint` if the formatter complains. Individual
targets are listed by `make help`.

`make lint` includes zizmor. Two release checks are worth running by hand when
you touch [`.releaserc.json`](.releaserc.json) or the release scripts:

```bash
npm run release:verify-notes
npm run release:dry
```

The first renders release notes through the configured plugin with no token
and no git access. It exists because a changelog preset bumped past the writer
version semantic-release pins does not raise an error, it silently renders
notes with every commit missing. CI runs it on every pull request, including
Dependabot's, which the full dry run cannot cover: those get a read-only token
and semantic-release verifies push access before it analyzes anything.

## Commit Messages

[Conventional Commits](https://www.conventionalcommits.org/), enforced by
[`hooks/conventional-commits.py`](hooks/conventional-commits.py) and consumed
by `semantic-release`. The type decides the release:

| Type | Release | Use for |
|------|---------|---------|
| `feat` | minor | A new rule, standard, skill, hook, or agent |
| `fix` | patch | A hook that misfires, a broken cross-reference, a wrong rule |
| `perf` | patch | A hook that got faster |
| `refactor` | patch | Restructuring with no behavior change |
| `revert` | patch | Undoing a previous change |
| `docs`, `test`, `style`, `build`, `ci`, `chore` | none | Everything else |

A breaking change adds `!` after the type or a `BREAKING CHANGE:` footer, and
cuts a major. In this repository breaking means a rule that reverses previous
guidance, a removed bypass variable, or a hook that now blocks something it
used to allow.

Two things never appear in a commit message, a pull request description, or a
code comment, and both are blocked by hooks:

- AI attribution of any kind, including `Co-authored-by` trailers.
- Workflow process language: phase numbers, references to a planning document,
  or paths into a spec folder.

## Writing Rules and Standards

Prose in this repository follows the same discipline the rules describe.

- Normative statements use one keyword from
  [`rules/normative-keywords.md`](rules/normative-keywords.md). Lowercase is
  the default.
- Every mention of a file that exists in the repository is a Markdown link.
  Enforced by
  [`.github/scripts/validate-markdown-links.py`](.github/scripts/validate-markdown-links.py).
- No em dashes, no parentheses in prose outside the four documented carve-outs,
  no emoji, no ASCII diagrams. Use Mermaid when a diagram is needed.
- A new rule is registered in [`rules/index.yml`](rules/index.yml) with its
  triggers, or it never loads.

## Writing Hooks

A hook runs on someone's machine, on every matching tool call, with their
privileges. It gets the strictest review in the repository.

- Fail open on an internal error. A crashing hook must never block unrelated
  work.
- Stay fast. The benchmark gate in CI holds hooks under 500 ms.
- Ship tests under [`tests/hooks/<hook-name>/`](tests) covering the block case,
  the allow case, and the bypass.
- Provide exactly one bypass, named `<HOOK_NAME>_DISABLE=1`, and document it in
  the rule that owns the hook.
- Never invent a source-comment marker to suppress a hook. Escape hatches live
  in the environment variable or the TTL registry, never in a contributor's
  source file.
- Register it in [`settings.json`](settings.json) and in the
  [`README.md`](README.md) hooks table.

## Source Comments

Project source carries no comments, in any language, including tests. Names,
types, and extracted functions carry the meaning instead. The one exception is
a directive a tool parses, such as `# noqa`, `// eslint-disable-next-line`, or
`# zizmor: ignore[...]`. Enforced by
[`hooks/comment-blocker.py`](hooks/comment-blocker.py).

Reasoning that would have gone in a comment belongs in the pull request
description, where reviewers read it and it cannot drift out of sync.

The workflow files under [`.github/workflows/`](.github/workflows) are
configuration rather than source, and do carry explanatory comments.

## Pull Requests

- One intent per pull request. If the description needs several "and also"
  clauses, split it.
- Open a draft early if you want feedback on direction.
- Keep the diff surgical. Unrelated cleanup in the same diff costs the reviewer
  time verifying lines nobody asked for.
- A problem that CI surfaces is in scope for your pull request even if you did
  not introduce it. See [`rules/found-fix.md`](rules/found-fix.md).
- Update [`README.md`](README.md) counts when you add a rule, standard, skill,
  hook, or agent. `validate-counts.py` fails the build otherwise.

## Releases

You do not tag anything. Merging to `main` triggers CI; a green CI triggers
[`.github/workflows/release.yml`](.github/workflows/release.yml), which
computes the version from your commit types, tags it, syncs the version into
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) and both
plugin manifests, and publishes GitHub release notes.

[`CHANGELOG.md`](CHANGELOG.md) is written by hand and is not generated. It
carries the narrative that generated notes cannot: what changed in the thinking
and why. Add an entry there when your change is substantial enough to deserve
one.

## Code of Conduct

Participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

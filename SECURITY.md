# Security Policy

## Reporting a Vulnerability

Report privately through GitHub Security Advisories:

1. Open <https://github.com/gufranco/claude-engineering-rules/security/advisories/new>.
2. Describe the issue, the affected file, and the impact.
3. Include reproduction steps and the commit you tested against.

Do not open a public issue for a vulnerability. A public issue is visible to
everyone before a fix exists.

Expect an acknowledgement within 5 business days and an assessment within 10.
There is no bounty programme.

## Supported Versions

This repository ships configuration rather than a runtime library. Only the
latest release on `main` receives fixes. Older tags are historical.

| Version | Supported |
|---------|-----------|
| Latest release | yes |
| Anything older | no |

## Threat Model

The product is a set of rules, runtime hooks, and skills loaded by Claude Code
on a developer workstation. Two consequences follow.

**Hooks execute with the developer's own privileges.** A hook that shells out
unsafely, or that is tricked into approving a destructive command, runs as the
person who installed it. Findings in [`hooks/`](hooks) are treated as the
highest severity class in this repository.

**Hooks are advisory, never a sandbox.** They intercept the tool calls they
have patterns for. An equivalent command the patterns do not cover is not
blocked. They exist to stop an accidental destructive action, never to contain
a determined attacker or untrusted code. Use container or VM isolation for
that. A report that a specific dangerous command bypasses a blocker is a
welcome bug report; a report that hooks are bypassable in principle is a
documented limitation.

**Rules and standards are text loaded into a model's context.** A rule that
instructs an agent to exfiltrate data or weaken a security control is a
vulnerability in this repository even though no code executes.

## What Is Not a Vulnerability

- A hook producing a false positive that blocks legitimate work. That is a bug;
  open an issue.
- A documented bypass environment variable. Each one is a deliberate escape
  hatch, listed in the rule that owns it.
- A dependency advisory whose vulnerable code path is unreachable, per the
  section below.

## Supply Chain

| Control | Where |
|---------|-------|
| GitHub's own actions pinned to a release tag, third-party actions to a full commit SHA, enforced by zizmor | [`.github/workflows/`](.github/workflows), [`.github/zizmor.yml`](.github/zizmor.yml) |
| Network egress of every job recorded by harden-runner in audit mode | [`.github/workflows/`](.github/workflows) |
| Automated action and Node bumps | [`.github/dependabot.yml`](.github/dependabot.yml) |
| Automated Python, pre-commit and runner image bumps | [`renovate.json`](renovate.json) |
| Static analysis of the workflows themselves | `zizmor` in the CI lint job |
| Code scanning | CodeQL, `security-extended` query suite |
| Dependency advisories on every pull request | `actions/dependency-review-action` |
| Supply-chain posture scoring | [`.github/workflows/scorecard.yml`](.github/workflows/scorecard.yml) |
| Python toolchain locked with hashes, installed with `uv sync --locked` | [`pyproject.toml`](pyproject.toml), [`uv.lock`](uv.lock) |
| Node toolchain locked with integrity hashes, installed with `pnpm install --frozen-lockfile` | [`package.json`](package.json), [`pnpm-lock.yaml`](pnpm-lock.yaml) |
| Registry signatures of every installed Node package | `pnpm audit signatures` in the release-config job |
| Secret scanning before commit | [`hooks/secret-scanner.py`](hooks/secret-scanner.py) |

### The `@semantic-release/npm` override

[`pnpm-workspace.yaml`](pnpm-workspace.yaml) carries this override:

```yaml
overrides:
  "@semantic-release/npm": "npm:@semantic-release/exec@7.1.0"
```

`semantic-release` depends on `@semantic-release/npm` unconditionally, and that
plugin vendors the entire npm CLI so it can publish packages. The vendored CLI
bundles its own dependency tree, which at the time of writing carries seven
advisories, two of them high. Bundled dependencies cannot be replaced by a
version override, and upgrading the npm CLI does not help because the current
release bundles the same versions.

This repository publishes nothing to any registry. `@semantic-release/npm` is
not listed in [`.releaserc.json`](.releaserc.json), so the plugin never loads
and the vendored CLI never runs. Rather than carry unreachable vulnerable code
in the tree, the override aliases the unused plugin to one already present.
In [`pnpm-lock.yaml`](pnpm-lock.yaml) the `@semantic-release/npm` slot
resolves to `@semantic-release/exec`, so the vendored CLI and its bundled tree
are absent.

The release pipeline verifies this arrangement rather than assuming it. The
`release-config` job in [`ci.yml`](.github/workflows/ci.yml) runs on every pull
request and every push to `main`:

- `pnpm audit --json` piped into
  [`audit-release-toolchain.py`](.github/scripts/audit-release-toolchain.py),
  which fails on any high or critical advisory and fails closed when the
  output is not a pnpm advisories report.
- `pnpm audit signatures`, which fails when an installed package lacks a valid
  registry signature.
- [`verify-release-notes.mjs`](scripts/verify-release-notes.mjs), which renders release notes through the
  configured plugin with no token.
- `semantic-release --dry-run --no-ci`, on push events only, because pull
  requests from forks and Dependabot get a read-only token and semantic-release
  checks push access first.

A future version that genuinely needs the real plugin fails in CI instead of
during a release.

Revisit the override when `semantic-release` stops depending on
`@semantic-release/npm`, or when the bundled advisories are resolved upstream.

### The `re2js` and `katex` overrides

`markdownlint-cli2` 0.24.0 reaches `re2js` 2.8.6, GHSA-gg6h-894w-4m9c, high,
and `katex` 0.16.47, GHSA-238p-pmpm-9mq7, low, through `markdownlint`. The two
overrides in [`pnpm-workspace.yaml`](pnpm-workspace.yaml) lift them to 2.9.1
and 0.19.1, the patched releases. Drop each one once `markdownlint` depends on
a patched range.

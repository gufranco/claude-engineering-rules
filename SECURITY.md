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
| Every GitHub Action pinned to a full commit SHA | [`.github/workflows/`](.github/workflows) |
| Automated dependency and action bumps | [`.github/dependabot.yml`](.github/dependabot.yml) |
| Static analysis of the workflows themselves | `zizmor` in the CI lint job |
| Code scanning | CodeQL, `security-extended` query suite |
| Dependency advisories on every pull request | `actions/dependency-review-action` |
| Supply-chain posture scoring | [`.github/workflows/scorecard.yml`](.github/workflows/scorecard.yml) |
| Pinned Python toolchain | [`requirements-dev.txt`](requirements-dev.txt) |
| Pinned Node toolchain with committed lockfile | [`package.json`](package.json), `package-lock.json` |
| Secret scanning before commit | [`hooks/secret-scanner.py`](hooks/secret-scanner.py) |

### The `@semantic-release/npm` override

[`package.json`](package.json) carries one `overrides` entry:

```json
"overrides": { "@semantic-release/npm": "npm:@semantic-release/exec@7.1.0" }
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
In [`package-lock.json`](package-lock.json) the `@semantic-release/npm` slot
resolves to `@semantic-release/exec`, so the vendored CLI and its bundled tree
are absent.

The release pipeline verifies this arrangement rather than assuming it. The
`release-config` job in [`ci.yml`](.github/workflows/ci.yml) runs on every pull
request and every push to `main`:

- `npm audit --json` piped into
  [`audit-release-toolchain.py`](.github/scripts/audit-release-toolchain.py),
  which fails on any high or critical advisory except the named waivers in that
  script, and fails on a waived one once npm reports a fix.
- [`verify-release-notes.mjs`](scripts/verify-release-notes.mjs), which renders release notes through the
  configured plugin with no token.
- `semantic-release --dry-run --no-ci`, on push events only, because pull
  requests from forks and Dependabot get a read-only token and semantic-release
  checks push access first.

A future version that genuinely needs the real plugin fails in CI instead of
during a release.

Revisit the override when `semantic-release` stops depending on
`@semantic-release/npm`, or when the bundled advisories are resolved upstream.

---
name: audit
description: Security audit across dependencies, secrets, Docker, code patterns, and images. Subcommands absorb /deps for vulnerability scanning, outdated packages, and deep scanning with trivy/snyk/gitleaks.
---

Multi-layer security audit and dependency management. Replaces standalone `/audit` and `/deps` skills.

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/audit` | Run all audit layers (deps, secrets, docker, code) |
| `/audit deps` | Dependency vulnerability scan |
| `/audit deps outdated` | List packages with newer versions |
| `/audit deps update [pkg]` | Update packages with approval |
| `/audit secrets` | Secret scanning across the full repo |
| `/audit docker` | Dockerfile security checks |
| `/audit code` | Code pattern analysis (injection, XSS, etc.) |
| `/audit scan` | Deep scan with trivy/snyk/gitleaks |
| `/audit image <name>` | Docker image vulnerability and layer analysis |

If no subcommand is given, run all layers.

---

## Full Audit (default)

### Steps

1. **Detect project and tools** (parallel): identify languages from manifests, check for Dockerfiles, check available tools (`pnpm`, `pip-audit`, `cargo-audit`, `trivy`, `grype`, `semgrep`, `bandit`), read `.env.example`.
2. **Dependency scan**: per-language audit (see deps section).
3. **Secret scanning**: scan all tracked files (`git ls-files`) using patterns from `~/.claude/hooks/secret-scanner.py`. Skip binaries, lockfiles, vendored code. Check `.gitignore` covers `.env`, `*.pem`, `*.key`.
4. **Dockerfile checks**: for each Dockerfile: pinned base image? `USER` directive? No `COPY` of sensitive files? `--no-install-recommends`? `HEALTHCHECK`? If `trivy` available, scan built images.
5. **Code patterns**: SQL injection (string concatenation in queries), command injection (`exec`/`spawn`/`eval` with dynamic input), XSS (`dangerouslySetInnerHTML`/`innerHTML`), path traversal, hardcoded secrets, insecure randomness (`Math.random()` for security), empty catch blocks. Run `semgrep --config auto` if available.
6. **Compile report** by severity:

```
## Security Audit Report

**Project:** <name>
**Date:** <date>
**Layers scanned:** dependencies, secrets, docker, code

### Critical (fix immediately)
### High (fix before next release)
### Medium (schedule fix)
### Low (backlog)

### Summary
| Layer | Critical | High | Medium | Low |
|-------|----------|------|--------|-----|

### Missing safeguards
- [ ] .gitignore covers .env and credential files
- [ ] .env.example documents all required env vars
- [ ] Dockerfiles use non-root user
- [ ] Dependencies have no critical vulnerabilities
```

7. **Suggest next steps** per finding severity.

---

## deps

Audit dependencies for known vulnerabilities. Detect package manager from lockfile.

### Package Manager Detection

`bun.lock`/`bun.lockb` = bun, `pnpm-lock.yaml` = pnpm, `yarn.lock` = yarn, `package-lock.json` = npm, `Cargo.toml` = cargo, `go.mod` = go, `pyproject.toml` with `uv.lock` = uv, `pyproject.toml` with `[tool.poetry]` = poetry, `pyproject.toml`/`requirements.txt` = pip. Also check for `Makefile`/`Justfile` targets.

### Audit (default)

Run language-specific audit: `pnpm audit`, `pip-audit`, `cargo audit`, `govulncheck ./...`. Parse and present by severity.

### outdated

Run `pnpm outdated`, `cargo outdated`, `go list -m -u all`, etc. Show current, wanted, and latest versions.

### update [package]

Show what would change, ask for approval, run update, re-audit to verify no new vulnerabilities.

### scan (deep)

Check available tools (parallel): `trivy`, `snyk`, `gitleaks`. Run all available:
- `trivy fs .` for dependency + config + secret scanning.
- `snyk test` + `snyk code test` for dependency + static analysis.
- `gitleaks detect --source .` for hardcoded secrets.

### image <name>

- `trivy image <name>` for OS and library vulnerabilities.
- `dive <name>` for layer analysis and wasted space.

---

## Rules

- Never install scanning tools without asking. Report availability.
- Never modify code or fix vulnerabilities automatically. Report and let user decide.
- Never expose actual secret values. Show file, line number, pattern name only.
- Always scan `.env.example`, never `.env` directly.
- Always detect package manager from lockfile.
- Never update packages without showing changes and getting approval.
- Never run `npm audit fix --force` without explicit approval.
- If no vulnerabilities found, say so clearly.
- Classify by actual severity, not quantity.

## Related skills

- `/review` -- Security-aware code review of specific changes.
- `/test` -- Run tests to verify security fixes.
- `/infra docker` -- Docker container management.

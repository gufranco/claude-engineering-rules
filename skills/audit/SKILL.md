---
name: audit
description: Security audit across dependencies, secrets, Docker, code patterns, and images. Subcommands absorb /deps for vulnerability scanning, outdated packages, and deep scanning with trivy/snyk/gitleaks. Use when user says "security audit", "scan for vulnerabilities", "check dependencies", "find secrets", "audit Docker", "CVE scan", or wants to find security issues across the full project. Do NOT use for code review (use /review), architecture completeness (use /assessment), or running tests (use /test).
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
| `/audit threat` | STRIDE threat modeling for the project or a specific component |

If no subcommand is given, run all layers (excluding threat modeling, which requires focused analysis).

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

1. **Suggest next steps** per finding severity.

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

## threat

STRIDE threat modeling for the full project or a specific component. Systematic analysis of security threats across six categories.

### When to use

- Before deploying a new service or API to production.
- When adding authentication, authorization, or data handling features.
- During security review of an existing system.
- When compliance or regulatory requirements demand threat analysis.

### Arguments

- No arguments: analyze the full project.
- `<component>`: focus on a specific module, service, or feature (e.g., `/audit threat auth`, `/audit threat payments`).

### Steps

1. **Map the attack surface.** Read the project structure and identify:
   - Entry points: API routes, webhooks, message consumers, CLI commands.
   - Data stores: databases, caches, file storage, session stores.
   - External integrations: third-party APIs, OAuth providers, payment processors.
   - Trust boundaries: where authenticated meets unauthenticated, where internal meets external.

2. **Analyze each STRIDE category.** For every entry point and data flow:

   | Category | Question | What to look for |
   |----------|----------|-----------------|
   | **S**poofing | Can an attacker impersonate a user or service? | Missing auth on endpoints, weak token validation, no mutual TLS between services |
   | **T**ampering | Can data be modified in transit or at rest? | Missing input validation, unsigned payloads, no integrity checks on stored data |
   | **R**epudiation | Can a user deny performing an action? | Missing audit logging, no transaction records, unsigned operations |
   | **I**nformation Disclosure | Can sensitive data leak? | Verbose error messages, exposed stack traces, missing field-level authorization |
   | **D**enial of Service | Can the system be overwhelmed? | Missing rate limits, unbounded queries, no payload size limits, resource-intensive operations without throttling |
   | **E**levation of Privilege | Can a user gain unauthorized access? | Missing authorization checks, IDOR vulnerabilities, role bypass, privilege escalation through API chaining |

3. **Score each finding.**

   | Severity | Criteria |
   |----------|---------|
   | Critical (9-10) | Exploitable without authentication, data breach risk |
   | High (7-8) | Exploitable with low-privilege access, significant impact |
   | Medium (4-6) | Requires specific conditions, moderate impact |
   | Low (1-3) | Theoretical risk, minimal impact |

4. **Generate the threat model report:**

   ```markdown
   ## STRIDE Threat Model

   **Scope:** <full project or component name>
   **Date:** <date GMT>
   **Entry points analyzed:** <count>

   ### Attack Surface Map
   <list of entry points, data stores, trust boundaries>

   ### Findings by Category

   #### Spoofing
   | # | Threat | Severity | Affected Component | Mitigation |
   |---|--------|----------|-------------------|------------|

   #### Tampering
   ...

   #### Repudiation
   ...

   #### Information Disclosure
   ...

   #### Denial of Service
   ...

   #### Elevation of Privilege
   ...

   ### Summary
   | Category | Critical | High | Medium | Low |
   |----------|----------|------|--------|-----|

   ### Priority Actions
   <findings rated 8+ must be resolved before shipping>
   ```

5. **Gate check.** Findings rated 8/10 or higher are blocking. State them explicitly and recommend resolution before deployment.

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

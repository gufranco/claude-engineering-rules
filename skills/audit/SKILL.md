---
name: audit
description: Security audit across dependencies, secrets, Docker, code patterns, images, STRIDE, and OWASP. Absorbs /deps for vulnerability scanning and /cso for threat modeling. Use when user says "security audit", "scan for vulnerabilities", "check dependencies", "find secrets", "audit Docker", "CVE scan", "cso", "threat model", "owasp audit", "deep security scan", or wants to find security issues across the full project. Do NOT use for code review (use /review), architecture completeness (use /assessment), or running tests (use /test).
---

Multi-layer security audit, dependency management, and threat modeling. Replaces standalone `/audit`, `/deps`, and `/cso` skills.

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
| `/audit daily` | High-confidence security gate: secrets archaeology, supply chain, CI/CD pipeline review |
| `/audit comprehensive` | Deep scan: daily checks plus OWASP Top 10, STRIDE per component, LLM/AI review |

If no subcommand is given, run all layers (excluding threat modeling, daily, and comprehensive, which require focused analysis).

---

## Full Audit (default)

### Steps

1. **Detect project and tools** (parallel): identify languages from manifests, check for Dockerfiles, check available tools (`pnpm`, `pip-audit`, `cargo-audit`, `trivy`, `grype`, `semgrep`, `bandit`), read `.env.example`.
2. **Dependency scan**: per-language audit (see deps section).
3. **Secret scanning**: scan all tracked files (`git ls-files`) using patterns from `~/.claude/hooks/secret-scanner.py`. Skip binaries, lockfiles, vendored code. Check `.gitignore` covers `.env`, `*.pem`, `*.key`. Apply the extended provider-specific patterns below (see secrets section) for Stripe, Twilio, GCP, Azure, Slack, Shopify, and other services not covered by the hook's generic patterns.
4. **Dockerfile checks**: for each Dockerfile: pinned base image? `USER` directive? No `COPY` of sensitive files? `--no-install-recommends`? `HEALTHCHECK`? If `trivy` available, scan built images.
5. **Code patterns**: SQL injection (string concatenation in queries), command injection (`exec`/`spawn`/`eval` with dynamic input), XSS (`dangerouslySetInnerHTML`/`innerHTML`), path traversal, hardcoded secrets, insecure randomness (`Math.random()` for security), empty catch blocks. Run `semgrep --config auto` if available. Also check supply chain risks: review `postinstall` scripts in dependencies (`cat node_modules/<pkg>/package.json | jq .scripts.postinstall`), verify scoped packages resolve to the private registry (`npm install --dry-run`), verify Docker secrets use `--mount=type=secret` not `ENV`/`ARG`, and confirm lockfile integrity hashes are present.
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

### Extended Secret Detection Patterns

Apply these provider-specific patterns during `secrets` and `scan` runs. These extend the generic patterns in `secret-scanner.py` with service-specific formats.

| Provider | Pattern | Severity |
|----------|---------|----------|
| AWS access key | `AKIA[0-9A-Z]{16}` | CRITICAL |
| Stripe | `sk_live_[a-zA-Z0-9]{24,}` or `pk_live_[a-zA-Z0-9]{24,}` | CRITICAL |
| Twilio | `AC[a-f0-9]{32}` or `SK[a-f0-9]{32}` | CRITICAL |
| GCP service account | `"type":\s*"service_account"` with `private_key_id` | CRITICAL |
| Azure storage | `AccountKey=[a-zA-Z0-9+/=]{88,}` | CRITICAL |
| Slack | `xoxb-[a-zA-Z0-9-]{50,}` or `hooks\.slack\.com/services/` | CRITICAL |
| GitHub PAT | `ghp_[a-zA-Z0-9]{36}` | CRITICAL |
| GitLab PAT | `glpat-[a-zA-Z0-9-]{20}` | CRITICAL |
| Shopify | `shppa_[a-z0-9]{32}` or `shpat_[a-z0-9]{32}` | CRITICAL |
| MongoDB Atlas | `mongodb\+srv://[^:]+:[^@]+@` | CRITICAL |
| Vault token | `s\.[a-zA-Z0-9]{24}` | CRITICAL |
| SendGrid | `SG\.[a-zA-Z0-9_-]{22,}` | CRITICAL |
| Firebase | `firebase-adminsdk` or `serviceAccount.json` | CRITICAL |
| npm registry | `//registry.npmjs.org/:_authToken` | CRITICAL |
| OpenAI | `sk-[a-zA-Z0-9]{48,}` | HIGH |
| Anthropic | `sk-ant-[a-zA-Z0-9_-]{48,}` | HIGH |
| Google Maps | `AIzaSy[a-zA-Z0-9_-]{33}` | HIGH |
| Datadog | `DD_API_KEY=[a-f0-9]{32}` | HIGH |
| Cloudflare | `CF_API_TOKEN=` or `X-Auth-Key:` | HIGH |
| Okta | `SSWS [a-zA-Z0-9_-]{40,}` | CRITICAL |

Also check high-risk contexts: test fixtures with real credentials, database seed files with production data, `.tfstate` files, Docker `ENV`/`ARG` with secrets, and `*.js.map` source maps containing decompiled secrets.

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

## daily

Fast security gate for routine use. Three focused checks that catch the highest-impact issues with minimal time investment.

### When to use

- Before merging a significant PR.
- As a periodic health check during active development.
- After onboarding a new dependency or changing CI configuration.

### Steps

1. **Secrets archaeology.** Search git history for leaked credentials:
   - Run `git log --all --diff-filter=A --name-only` to find added files.
   - Search for patterns: API keys, tokens, passwords, private keys, connection strings.
   - Check `.env` files that were committed and later removed but remain in history.
   - Check for high-entropy strings in configuration files.
   - Report each finding with the commit hash, file path, and pattern matched.

2. **Dependency supply chain check.** Audit the dependency tree:
   - Run the project's audit command: `npm audit`, `pnpm audit`, `pip audit`, `cargo audit`, or equivalent.
   - Check for known CVEs with severity >= HIGH.
   - Flag packages with fewer than 100 weekly downloads or a single maintainer.
   - Flag packages added in the last 30 days that have no prior release history.
   - Cross-reference lockfile integrity: verify the lockfile is committed and matches the manifest.

3. **CI/CD pipeline security review.** Audit workflow files:
   - Check for `pull_request_target` triggers with checkout of PR code, which enables code injection.
   - Check for secrets passed to steps that run user-controlled code.
   - Check for `actions/checkout` without pinned SHA versions.
   - Check for overly permissive `permissions` blocks.
   - Check for self-hosted runners on public repos.
   - Verify OIDC is used for cloud provider authentication where possible.

### Output

```
## Security Daily Report

**Date:** <timestamp GMT>
**Mode:** daily
**Duration:** <seconds>

### Secrets Archaeology
| Commit | File | Pattern | Severity |
|--------|------|---------|----------|
| <hash> | <path> | <type> | <1-10> |

### Supply Chain
| Package | Issue | CVE | Severity |
|---------|-------|-----|----------|
| <name> | <description> | <id or N/A> | <1-10> |

### CI/CD Pipeline
| File | Line | Issue | Severity |
|------|------|-------|----------|
| <path> | <line> | <description> | <1-10> |

### Verdict
<PASS: no blocking findings / BLOCK: N findings rated 8/10+>
```

---

## comprehensive

Deep scan that includes everything from daily mode plus OWASP Top 10, STRIDE threat modeling per component, and LLM/AI security review.

### When to use

- Monthly security review cadence.
- Before a major release or launch.
- After significant architecture changes.
- When onboarding a new team member who needs a security overview.

### Steps

1. **Run all daily checks.** Execute steps 1-3 from the daily mode.

2. **OWASP Top 10 audit.** Read `~/.claude/skills/security-patterns.md` as a vulnerability pattern catalog. Map each pattern to its OWASP category when checking the codebase:

   | Category | What to check |
   |----------|--------------|
   | A01: Broken Access Control | Authorization checks on every endpoint, IDOR prevention, CORS configuration |
   | A02: Cryptographic Failures | TLS usage, password hashing algorithms, sensitive data exposure in logs |
   | A03: Injection | SQL injection, XSS, command injection, LDAP injection, template injection |
   | A04: Insecure Design | Business logic flaws, missing rate limiting, missing abuse prevention |
   | A05: Security Misconfiguration | Default credentials, unnecessary features enabled, error messages leaking internals |
   | A06: Vulnerable Components | Outdated frameworks, known vulnerable versions, unmaintained dependencies |
   | A07: Authentication Failures | Weak password policies, missing MFA, session fixation, credential stuffing prevention |
   | A08: Data Integrity Failures | CI/CD pipeline integrity, unsigned updates, deserialization vulnerabilities |
   | A09: Logging Failures | Missing audit logs, sensitive data in logs, no alerting on security events |
   | A10: SSRF | Server-side request forgery via user-controlled URLs, DNS rebinding |

3. **STRIDE threat modeling.** For each major component identified in the codebase:

   | Threat | Question | What to check |
   |--------|----------|--------------|
   | Spoofing | Can an attacker pretend to be someone else? | Authentication mechanisms, token validation, certificate pinning |
   | Tampering | Can an attacker modify data in transit or at rest? | Input validation, integrity checks, signed payloads |
   | Repudiation | Can an attacker deny performing an action? | Audit logging, non-repudiation controls, tamper-evident logs |
   | Information Disclosure | Can an attacker access data they should not see? | Authorization boundaries, error messages, debug endpoints, log contents |
   | Denial of Service | Can an attacker make the system unavailable? | Rate limiting, resource quotas, payload size limits, algorithmic complexity |
   | Elevation of Privilege | Can an attacker gain higher access than intended? | Role checks, privilege escalation paths, default permissions |

   Produce a threat matrix entry for each component-threat combination that has a non-trivial risk.

4. **LLM/AI security review.** If the project uses LLMs or AI models:
   - Check for prompt injection vulnerabilities in user-facing inputs.
   - Check for sensitive data leakage through model context or logs.
   - Check for missing output sanitization on model responses.
   - Check for excessive permissions granted to AI agents or tools.
   - Check for missing rate limiting on model API calls.
   - Skip this section entirely if the project does not use LLM or AI features.

### Output

```
## Security Comprehensive Report

**Date:** <timestamp GMT>
**Mode:** comprehensive
**Duration:** <minutes>

### Daily Checks
<Include full daily report sections>

### OWASP Top 10 Audit
| Category | Status | Findings | Severity |
|----------|--------|----------|----------|
| A01: Broken Access Control | PASS/FAIL | <description> | <1-10> |
| A02: Cryptographic Failures | PASS/FAIL | <description> | <1-10> |
| ... | ... | ... | ... |

### STRIDE Threat Matrix
| Component | Threat | Likelihood | Severity | Mitigation |
|-----------|--------|-----------|----------|------------|
| <name> | <S/T/R/I/D/E> | <low/medium/high> | <1-10> | <action> |

### LLM/AI Security
| Finding | Severity | Mitigation |
|---------|----------|------------|
| <description> | <1-10> | <action> |
(or "Not applicable: no LLM/AI features detected.")

### Summary
**Total findings:** <count>
**Blocking (8/10+):** <count>
**Action items:** <numbered list>

### Verdict
<PASS: no blocking findings / BLOCK: N findings rated 8/10+ require remediation>
```

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

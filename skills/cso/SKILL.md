---
name: cso
description: Chief Security Officer audit with STRIDE and OWASP. Two modes: daily (default, high-confidence gate, fast) and comprehensive (monthly deep scan). Covers secrets archaeology, supply chain, CI/CD pipeline security, OWASP Top 10, STRIDE threat modeling, and LLM/AI security. Use when user says "cso", "security audit stride", "threat model", "owasp audit", "security review", "deep security scan", or wants a structured security assessment beyond dependency scanning. Do NOT use for dependency-only checks (use /audit), code review (use /review), or incident response (use /incident).
---

Chief Security Officer audit skill. Runs a structured security assessment using STRIDE threat modeling and OWASP Top 10, producing a threat matrix with severity ratings and actionable mitigations.

## Mode Routing

| Invocation | Action |
|-----------|--------|
| `/cso` or `/cso daily` | High-confidence gate: secrets, supply chain, CI/CD pipeline review |
| `/cso comprehensive` | Monthly deep scan: daily checks plus OWASP Top 10, STRIDE per component, LLM/AI review |

If no mode is given, default to `daily`.

---

## daily

Fast security gate for routine use. Runs three focused checks that catch the highest-impact issues with minimal time investment.

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
## CSO Daily Report

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

Monthly deep scan that includes everything from daily mode plus OWASP Top 10, STRIDE threat modeling, and LLM/AI security review.

### When to use

- Monthly security review cadence.
- Before a major release or launch.
- After significant architecture changes.
- When onboarding a new team member who needs a security overview.

### Steps

1. **Run all daily checks.** Execute steps 1-3 from the daily mode.

2. **OWASP Top 10 audit.** Check each category against the codebase:

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
## CSO Comprehensive Report

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

## Rules

- Findings rated 8/10 or higher in severity are blocking. The audit does not pass until they are resolved.
- Never access production systems or databases directly. Analyze code and configuration only.
- All timestamps in GMT.
- Prefix every `gh` or `glab` command with the appropriate token per `../../rules/github-accounts.md` or `../../rules/gitlab-accounts.md`.
- When a finding requires a code change, provide the specific file, line, and recommended fix.
- Do not report theoretical risks with no evidence in the codebase. Every finding must reference a specific file or configuration.
- STRIDE modeling applies only to components identified in the current codebase, not hypothetical future components.

## Related skills

- `/audit` -- Dependency-focused security scanning.
- `/review` -- Code review with security as one of many categories.
- `/ship` -- Ship code after security checks pass.
- `/incident` -- Document incidents caused by security issues.

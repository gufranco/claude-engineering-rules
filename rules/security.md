# Security

## Secrets and Environment

**NEVER commit:** `.env`, `*.pem`, `*.key`, `credentials.json`, `id_rsa`

- Required env vars MUST be documented in `.env.example` with placeholder values
- Validate required env at startup. Fail fast with a clear message listing what is missing.
- **Env vars are a shared attack surface.** Every dependency in the process can read the full environment. A single compromised transitive package can exfiltrate all secrets via the process environment. Mitigations: grant each service only the secrets it needs, restrict container outbound network access, run high-privilege operations in separate processes with minimal dependencies

## Auth Checklist

- [ ] Passwords hashed (bcrypt/argon2)
- [ ] Rate limiting on auth endpoints
- [ ] Token expiration configured
- [ ] Permission check on every request
- [ ] CSRF protection on state-changing endpoints (SameSite cookies, CSRF tokens, or origin validation)
- [ ] Principle of least privilege: every component, user, and service account has only the permissions it needs, nothing more

## Auth Delegation

Prefer specialized identity providers (Auth0, Cognito, Clerk, Keycloak) over custom auth. Auth flows have too many moving parts: password hashing, token lifecycle, session management, MFA, rate limiting, account recovery. A single mistake creates a vulnerability.

When delegating: separate the auth concern behind an interface so the provider can be swapped without rewriting business logic. Record the trade-off (vendor coupling, privacy, cost) in an ADR.

## Access Control

- Default deny. Explicitly grant permissions, never explicitly deny them
- Verify authorization per-resource, not just per-role. User A being an admin does not mean they can access User B's private data (IDOR prevention)
- Use role-based access control (RBAC) for most applications. Consider attribute-based (ABAC) when permissions depend on resource properties or context
- Authorization logic lives in one place, not scattered across controllers

## Encryption

| Layer | Requirement |
|-------|-------------|
| In transit | TLS 1.2+ on all external connections. No plaintext HTTP for APIs. Enforce HTTPS redirects |
| At rest | Encrypt sensitive data in databases and object storage. Use platform-managed keys (AWS KMS, GCP KMS) unless you have a specific reason to manage your own |
| Application | Hash passwords with bcrypt or argon2. Never use MD5 or SHA for password storage. Use constant-time comparison for secrets |

## Data Privacy

When handling personal data, design for compliance from the start:

- **Data minimization**: collect only what you need. Do not store data "just in case"
- **Retention policy**: define how long each type of personal data is kept. Automate deletion after the retention period
- **Right to erasure**: build a way to delete all of a user's personal data on request. Soft delete is not enough for privacy compliance; the data must be truly gone or anonymized
- **Consent**: if data use requires consent, record when and what was consented to. Make withdrawal easy
- **Audit trail**: log who accessed personal data, when, and why

Applies regardless of GDPR, LGPD, CCPA coverage. Building later is always harder.

## Audit Logging

Log sensitive actions with context:

- Login attempts (success/failure)
- Password changes
- Role changes
- Record deletions
- Permission changes
- Personal data access and exports

Format: `{ action, userId, targetId, timestamp, ip, userAgent }`

## Web Security Headers

Set security headers on every HTTP response. Missing headers are silent vulnerabilities that scanners catch but developers miss.

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` | Force HTTPS for 2 years, include subdomains |
| `Content-Security-Policy` | Start with `default-src 'self'`, loosen as needed | Prevent XSS by controlling resource origins |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `DENY` or `SAMEORIGIN` | Prevent clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer information leakage |
| `Permissions-Policy` | Disable unused APIs: `camera=(), microphone=(), geolocation=()` | Restrict browser feature access |

Use a framework middleware or reverse proxy to set these once, not per-route.

## Input and Output Safety

- **Payload size limits**: enforce maximum request body size at the framework or reverse proxy level. Unbounded payloads enable denial of service. Default to a reasonable limit (e.g., 1MB) and increase per-endpoint only when justified
- **Output encoding**: encode all user-supplied data before rendering into HTML, JavaScript, CSS, or SQL. Use framework-provided escaping by default. Manual string concatenation into templates is a bug
- **ReDoS prevention**: avoid unbounded quantifiers in regex patterns that process user input. Patterns like `(a+)+$` or `([a-zA-Z]+)*` backtrack exponentially. Use linear-time regex engines or validate input length before matching
- **Dynamic code execution**: never use `eval()`, `Function()`, `exec()`, or equivalent constructs that execute strings as code. If dynamic behavior is needed, use a lookup table or strategy pattern
- **Open redirect prevention**: validate redirect destinations against an allowlist of trusted domains. Never redirect to a URL taken directly from user input without validation. Relative paths are safer than absolute URLs
- **SSRF prevention**: when the server fetches URLs on behalf of user input, allowlist permitted domains and protocols. Block requests to private IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x, ::1) and cloud metadata endpoints (169.254.169.254). Validate the resolved IP, not just the hostname, to prevent DNS rebinding

## Token Revocation

JWTs cannot be invalidated without server-side state. When revocation is required:

- Maintain a blocklist of revoked token IDs (the `jti` claim) in a fast store like Redis
- Set a TTL on blocklist entries matching the token's remaining lifetime
- Check the blocklist on every authenticated request
- Revoke tokens on: password change, explicit logout, permission change, account compromise

Short-lived access tokens (5-15 minutes) with refresh token rotation reduce the window of exposure and the size of the blocklist.

## Process Isolation

- Run as non-root. Container root = host root if the container is escaped
- In containers: create a dedicated user in the Dockerfile (`USER node`, `USER appuser`), never run as PID 1 without signal handling
- In VMs and bare metal: create a service account with only the permissions the application needs
- File system: application must own only its working directory. System dirs, config outside the app, and other users' data must be inaccessible

## Supply Chain Security

Dependencies are attack surface. A compromised package runs with your code's permissions.

- **Lock dependencies**: always commit lockfiles. Pin exact versions, not ranges
- **Verify integrity**: enable lockfile integrity checking (`npm ci`, not `npm install` in CI)
- **Review before adding**: check the package's maintainers, recent commits, download count, and known vulnerabilities before installing. A package with 12 downloads and one maintainer is a risk
- **Typosquatting**: double-check package names. `lodash` vs `1odash`, `colors` vs `colour`. One character can mean malicious code
- **Dependency confusion**: if you use private packages, configure scoped registries to prevent public registry substitution
- **Audit regularly**: run `npm audit`, `pip audit`, or equivalent in CI. Block builds on critical/high vulnerabilities
- **Minimize surface**: fewer dependencies = fewer attack vectors. Prefer native/stdlib when the alternative is a small package with deep transitive dependencies
- **Monitor advisories**: subscribe to security advisories for your critical dependencies. Do not wait for a scheduled audit to learn about a zero-day

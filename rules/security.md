# Security

## Secrets and Environment

**NEVER commit:** `.env`, `*.pem`, `*.key`, `credentials.json`, `id_rsa`

- Required env vars MUST be documented in `.env.example` with placeholder values
- Validate required env at startup. Fail fast with a clear message listing what is missing
- Grant each service only the secrets it needs. Restrict container outbound network access. Run high-privilege operations in separate processes with minimal dependencies

## Auth Checklist

Apply `checklists/checklist.md` category 33 (Security and Access Control).

## OAuth 2.1 and Token Management

- PKCE is mandatory for all OAuth flows. Use S256 code challenge method. Generate code verifiers with `crypto.randomBytes(32)`
- Access tokens: 15-minute maximum lifetime, RS256 signing, validate `aud` and `iss` claims on every request. Store in memory only, never localStorage
- Refresh tokens: httpOnly + secure + sameSite cookies. Rotate after each use. Invalidate previous token immediately. Track token family for replay detection

## Passkeys and FIDO2

- Set `userVerification: 'required'`
- Validate authenticator counter increment on every authentication. Counter regression indicates a cloned authenticator
- Support multiple passkeys per user for backup
- Use synced passkeys for convenience, device-bound for high-security flows

## Password Policy (NIST 800-63B)

- Minimum 12 characters, no maximum below 64
- No complexity requirements (uppercase, special chars, numbers)
- No periodic rotation requirements
- Check against HaveIBeenPwned breach database on creation and change
- Hash with Argon2id (`timeCost: 3, memoryCost: 65536, parallelism: 4`) or bcrypt with saltRounds >= 12

## Auth Rate Limits

| Endpoint | Limit | Lockout |
|----------|-------|---------|
| Login attempts | 5 failures | 15-minute lockout per account |
| Password resets | 3 per hour | Per email address |
| Token refreshes | 10 per minute | Per user |
| Account creation | 3 per hour | Per IP address |

## Auth Delegation

Prefer specialized identity providers (Auth0, Cognito, Clerk, Keycloak) over custom auth. Separate the auth concern behind an interface so the provider can be swapped without rewriting business logic. Record the trade-off in an ADR.

## Access Control

- Default deny. Explicitly grant permissions, never explicitly deny them
- Verify authorization per-resource, not just per-role. User A being an admin does not mean they can access User B's private data (IDOR prevention)
- Use RBAC for most applications. Consider ABAC when permissions depend on resource properties or context
- Authorization logic lives in one place, not scattered across controllers

## Encryption

| Layer | Requirement |
|-------|-------------|
| In transit | TLS 1.2+ on all external connections. No plaintext HTTP for APIs. Enforce HTTPS redirects |
| At rest | Encrypt sensitive data in databases and object storage. Use platform-managed keys (AWS KMS, GCP KMS) |
| Application | Hash passwords with bcrypt or argon2. Never MD5, SHA-1, or SHA-256 for password storage. Use constant-time comparison for secrets |

## Data Privacy

- **Data minimization**: collect only what you need. Do not store data "just in case"
- **Retention policy**: define how long each type of personal data is kept. Automate deletion after the retention period
- **Right to erasure**: build a way to delete all of a user's personal data on request. Soft delete is not enough; the data must be truly gone or anonymized
- **Consent**: if data use requires consent, record when and what was consented to. Make withdrawal easy
- **Audit trail**: log who accessed personal data, when, and why

## Audit Logging

Log sensitive actions with context. Format: `{ action, userId, targetId, timestamp, ip, userAgent }`

- Login attempts (success/failure), password changes, role changes
- Record deletions, permission changes, personal data access and exports

## Web Security Headers

Set on every HTTP response via framework middleware or reverse proxy, not per-route.

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` | Force HTTPS for 2 years |
| `Content-Security-Policy` | Start with `default-src 'self'`, loosen as needed | Prevent XSS |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `DENY` or `SAMEORIGIN` | Prevent clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Restrict browser feature access |

## Input and Output Safety

- **Payload size limits**: enforce maximum request body size at the framework or reverse proxy level. Default to 1MB and increase per-endpoint only when justified
- **Output encoding**: encode all user-supplied data before rendering into HTML, JavaScript, CSS, or SQL. Manual string concatenation into templates is a bug
- **ReDoS prevention**: avoid unbounded quantifiers in regex patterns that process user input (`(a+)+$`, `([a-zA-Z]+)*`). Use linear-time engines or validate input length first
- **Dynamic code execution**: never use `eval()`, `Function()`, `exec()`, or equivalent. Use lookup tables or strategy patterns
- **Open redirect prevention**: validate redirect destinations against an allowlist of trusted domains. Never redirect to a URL from user input without validation
- **SSRF prevention**: when fetching URLs from user input, allowlist permitted domains and protocols. Block private IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x, ::1) and cloud metadata endpoints (169.254.169.254). Validate the resolved IP, not just the hostname

## Token Revocation

- Maintain a blocklist of revoked `jti` claims in Redis with TTL matching the token's remaining lifetime
- Check the blocklist on every authenticated request
- Revoke tokens on: password change, explicit logout, permission change, account compromise
- Short-lived access tokens (5-15 minutes) with refresh token rotation reduce exposure window and blocklist size

## Process Isolation

- Run as non-root. Container root = host root if the container is escaped
- In containers: create a dedicated user (`USER node`), never run as PID 1 without signal handling
- In VMs and bare metal: create a service account with only the permissions the application needs
- Application must own only its working directory

## Secrets Management

- Use dynamic secrets with TTL-based rotation: HashiCorp Vault, Infisical, or OpenBao
- For Kubernetes: use External Secrets Operator to sync from external stores into native Kubernetes Secrets
- Never store static long-lived secrets in production environment variables
- Automate rotation. Define rotation schedules per secret type, trigger on suspected compromise
- Document how to revoke and rotate all secrets within 1 hour (emergency revocation procedure)
- Separate secret stores for dev, staging, and production

## Supply Chain Security

- **Lock dependencies**: always commit lockfiles. Pin exact versions, not ranges
- **Verify integrity**: use `npm ci`, not `npm install` in CI
- **Review before adding**: check maintainers, recent commits, download count, and known vulnerabilities. A package with 12 downloads and one maintainer is a risk
- **Typosquatting**: double-check package names. One character can mean malicious code
- **Dependency confusion**: configure scoped registries when using private packages
- **Audit regularly**: run `npm audit`, `pip audit`, or equivalent in CI. Block builds on critical/high vulnerabilities
- **Minimize surface**: prefer native/stdlib over small packages with deep transitive dependencies
- **Monitor advisories**: subscribe to security advisories for critical dependencies
- **SBOM generation**: generate a Software Bill of Materials on every CI build using SPDX or CycloneDX format
- **Artifact signing**: sign build artifacts with Sigstore (cosign) for provenance verification
- **SLSA compliance**: target SLSA Level 2 minimum for customer-facing services

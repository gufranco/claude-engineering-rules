# Security

## Secrets and Environment

**NEVER commit:** `.env`, `*.pem`, `*.key`, `credentials.json`, `id_rsa`

- Required env vars MUST be documented in `.env.example` with placeholder values
- Validate required env at startup. Fail fast with a clear message listing what is missing.
- **Env vars are a shared attack surface.** Every dependency in the process can read the full environment. A single compromised transitive package can exfiltrate all secrets via the process environment. Mitigations: grant each service only the secrets it needs, restrict container outbound network access, run high-privilege operations in separate processes with minimal dependencies

## Auth Checklist

Apply `checklists/checklist.md` category 33 (Security and Access Control). The full auth verification items live there.

## OAuth 2.1 and Token Management

- PKCE is mandatory for all OAuth flows. Use S256 code challenge method. Generate code verifiers with `crypto.randomBytes(32)`
- Access tokens: 15-minute maximum lifetime, RS256 signing, validate `aud` and `iss` claims on every request. Store in memory only, never localStorage
- Refresh tokens: httpOnly + secure + sameSite cookies. Rotate after each use. Invalidate previous token immediately. Track token family for replay detection
- Short-lived access tokens with refresh token rotation reduce exposure window and blocklist size

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
| Application | Hash passwords with bcrypt or argon2 (dedicated key derivation functions). Never use standalone MD5, SHA-1, or SHA-256 for password storage: these are fast hashes, not password hashes. Use constant-time comparison for secrets |

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

## Secrets Management

Environment variables are insufficient for production secrets. A single compromised transitive package can read the full process environment.

- Use dynamic secrets with TTL-based rotation: HashiCorp Vault, Infisical, or OpenBao
- For Kubernetes: use External Secrets Operator to sync secrets from external stores into native Kubernetes Secrets
- Never store static long-lived secrets in production environment variables
- Automate rotation: define rotation schedules per secret type, trigger rotation on suspected compromise
- Emergency revocation procedure: document how to revoke and rotate all secrets within 1 hour
- Environment isolation: separate secret stores for dev, staging, and production

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
- **SBOM generation**: generate a Software Bill of Materials on every CI build using SPDX or CycloneDX format. Per-file SPDX-License-Identifier headers improve SBOM accuracy. See `rules/licensing.md`
- **Artifact signing**: sign build artifacts with Sigstore (cosign) for provenance verification
- **SLSA compliance**: target SLSA Level 2 minimum for customer-facing services (hosted builds with signed provenance)

## Hook Coverage

Runtime hooks in `~/.claude/hooks/` provide advisory enforcement against dangerous operations. They prevent accidental damage from model hallucination, not intentional bypass by a compromised agent.

| Category | Level | Hook | Pattern Count |
|----------|-------|------|--------------|
| Filesystem destruction (rm, dd, mkfs, shred) | Block | dangerous-command-blocker | 15 |
| Privilege escalation (sudo + destructive, setuid, sudoers) | Block | dangerous-command-blocker | 5 |
| Reverse shells (bash, nc, socat, python, perl, ruby) | Block | dangerous-command-blocker | 8 |
| Git destructive (force push, reset, filter-branch, reflog) | Block | dangerous-command-blocker | 13 |
| Cloud CLI: AWS (S3, EC2, RDS, Lambda, EKS, IAM, +10 more) | Block | dangerous-command-blocker | 18 |
| Cloud CLI: GCP (Compute, SQL, GKE, Functions, Run, Pub/Sub, Storage) | Block | dangerous-command-blocker | 9 |
| Cloud CLI: Azure (VMs, SQL, AKS, WebApps, Storage, KeyVault, CosmosDB) | Block | dangerous-command-blocker | 9 |
| Platform CLI (Vercel, Netlify, Firebase, Cloudflare, Fly.io, Heroku, Railway, Supabase) | Block | dangerous-command-blocker | 9 |
| Container (Docker privileged/prune/rm, Podman, Compose down -v) | Block | dangerous-command-blocker | 9 |
| Kubernetes (delete critical resources, drain, cordon, mass delete) | Block | dangerous-command-blocker | 6 |
| Helm (uninstall, rollback) | Block | dangerous-command-blocker | 2 |
| Database: Redis (FLUSHALL, FLUSHDB, CONFIG SET) | Block | dangerous-command-blocker | 4 |
| Database: MongoDB (dropDatabase, dropCollection, deleteMany all) | Block | dangerous-command-blocker | 2 |
| Database: PostgreSQL (dropdb, DROP DDL, pg_dump pipe) | Block | dangerous-command-blocker | 3 |
| Database: MySQL (drop, TRUNCATE, DROP DDL) | Block | dangerous-command-blocker | 3 |
| Database: SQLite (DROP, file deletion) | Block | dangerous-command-blocker | 2 |
| IaC: Terraform/OpenTofu (destroy, auto-approve, state rm, taint, force-unlock) | Block | dangerous-command-blocker | 8 |
| IaC: Pulumi (destroy, cancel, stack rm) | Block | dangerous-command-blocker | 3 |
| IaC: Ansible (production playbook, ad-hoc on prod) | Block | dangerous-command-blocker | 2 |
| IaC: CDK/Serverless/SAM/Copilot (destroy/remove/delete) | Block | dangerous-command-blocker | 4 |
| SQL statements (DELETE no WHERE, TRUNCATE, DROP, UPDATE no WHERE, ALTER DROP, GRANT/REVOKE ALL) | Block | dangerous-command-blocker | 7 |
| Secret exfiltration via commands (curl -d, scp, rsync credential files) | Block | dangerous-command-blocker | 3 |
| Cron and systemd (crontab -r, systemctl stop/disable) | Block | dangerous-command-blocker | 2 |
| Protected branch push (main, master, develop) | Block | dangerous-command-blocker | 1 |
| Secrets in staged files (40+ API key patterns) | Block | secret-scanner | 40+ |
| Env/credential file access (.env, .ssh, .aws, .gnupg, .kube, .tfstate, .pem, .key, .npmrc, .pypirc, .netrc) | Block | env-file-guard + permissions | 50+ |
| Large file commits (>5MB) | Block | large-file-blocker | 1 |
| gh/glab account safety (token guards) | Block | gh-token-guard, glab-token-guard | 2 |
| Docker context global switch (`docker context use`) | Block | docker-context-guard | 1 |
| Kubernetes context global switch (`kubectl config use-context`, `kubectx <name>`) | Block | kubectl-context-guard | 2 |
| AWS profile global write (`aws configure set` without `--profile`) | Block | aws-profile-guard | 1 |
| gcloud config global write (`gcloud config set`, `gcloud config configurations activate`) | Block | gcloud-config-guard | 2 |
| Terraform workspace global switch (`terraform workspace select` and `new`) | Block | terraform-workspace-guard | 2 |
| mise global tool mutation (`mise use --global`, `mise unuse --global`) | Block | mise-global-guard | 2 |
| Commit message format | Block | conventional-commits | 1 |

**Limitations:** hooks are advisory, not kernel-level enforcement. An agent could bypass a hook by using an equivalent command not covered by the patterns. For untrusted code execution, use container or VM isolation.

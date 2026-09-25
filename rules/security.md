# Security

Secrets never enter the repository, the logs, or the conversation; access is deny by default; every dependency is attack surface.

- Never commit `.env`, `*.pem`, `*.key`, `credentials.json`, `id_rsa`. Document required env vars in `.env.example` and fail fast at startup when one is missing.
- Never read a secret into the transcript. Pass it through the process: `curl -H "Authorization: $(cat file)"`, never `cat file`. Verify a property such as length, prefix, or a successful call, never the value. A secret that reaches the transcript is disclosed: say so and rotate.
- Never put a credential in a remote URL for clone, push, or remote add. Use a credential helper that reads the token at call time.
- When a capability must be broad, allow a narrowing wrapper that fails closed, never a wider wildcard permission.
- OAuth: PKCE with S256 always. Access tokens 15 minutes max, RS256, validate `aud` and `iss`, memory only, never localStorage. Refresh tokens in httpOnly, secure, sameSite cookies, rotated on every use.
- Passkeys: `userVerification: 'required'`, check counter increments, allow multiple per user.
- Passwords: 12 characters minimum, max at least 64, no complexity or rotation rules, breach-database check, Argon2id `timeCost: 3, memoryCost: 65536, parallelism: 4` or bcrypt saltRounds >= 12.
- Auth rate limits: 5 failed logins then 15-minute lockout, 3 resets per email per hour, 10 refreshes per user per minute, 3 signups per IP per hour.
- Default deny. Authorize per resource to prevent IDOR, in one place.
- TLS 1.2+ everywhere, encrypt sensitive data at rest, never MD5, SHA-1, or SHA-256 for passwords, constant-time secret comparison.
- Audit-log logins, password and role changes, deletions, and personal data access as `{ action, userId, targetId, timestamp, ip, userAgent }`.
- Set HSTS `max-age=63072000; includeSubDomains; preload`, nonce-based CSP with `'strict-dynamic'` and no `'unsafe-inline'` or `'unsafe-eval'`, `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`. Ship CSP report-only for one week first.
- Enforce request body limits, encode output, avoid ReDoS-prone regex, never `eval()`, allowlist redirect targets, block private IP ranges and `169.254.169.254` for server-side fetches.
- Revoke JWTs via a `jti` blocklist with TTL on logout, password change, permission change, or compromise.
- Run as non-root. Production secrets come from a secrets manager with rotation, not static env vars.
- Commit lockfiles, pin exact versions, use `npm ci`, run audits in CI blocking critical and high, check for typosquatting, generate an SBOM, sign artifacts.

Full rule, examples, and rationale: [`standards/security.md`](../standards/security.md). Read it before touching auth, tokens, headers, CSP, secrets storage, or personal data handling.

## Enforcement

Enforced by: [`hooks/dangerous-command-blocker.py`](../hooks/dangerous-command-blocker.py).
Enforced by: [`hooks/env-file-guard.py`](../hooks/env-file-guard.py).
Enforced by: [`hooks/secret-scanner.py`](../hooks/secret-scanner.py).

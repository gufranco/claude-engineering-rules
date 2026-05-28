# Cybersecurity Baseline

## Scope

Every frontend task. Loaded by default per [`compliance-defaults.md`](compliance-defaults.md). Composes with [`security.md`](security.md) which covers cross-cutting security (secrets, encryption, supply chain, auth). This rule covers the frontend-specific cybersecurity defaults.

## Mandatory Targets

| Target | Rule |
|--------|------|
| Transport | TLS 1.3 on new endpoints, TLS 1.2 grandfathered; HTTPS-only; HSTS preload + 2-year max-age |
| Cookies | `HttpOnly` + `Secure` + `SameSite=Lax` (or `Strict` for sensitive); `__Host-` prefix where applicable |
| CSP | Nonce-based with `strict-dynamic`, no `unsafe-inline`, no `unsafe-eval`; report-only for one week before enforcement |
| Headers | HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy; full table in [`security.md`](security.md) |
| Password | NIST 800-63B: 12 chars min, no complexity, no rotation, breach-database check; Argon2id or bcrypt saltRounds >= 12 |
| MFA | Mandatory for any account touching personal, payment, health, or admin data; passkey or TOTP preferred over SMS |
| Session timeout | 15 min sensitive, 60 min non-sensitive; warning + one-click extension |
| Rate limits | 5 login attempts / 15-min lockout; 3 password resets per email per hour; 3 account creations per IP per hour |
| Breach notification | 72h external + 4 business days SEC for reporting entities |
| Subresource integrity | `integrity` attribute on every external script and link |
| Mixed content | Forbidden; all subresources HTTPS |
| Open redirect | Allowlist destinations; never redirect to user-supplied URL |
| SSRF | Block private IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x, ::1) and cloud metadata (169.254.169.254) when fetching server-side |

## Breach Notification Timeline Matrix

| Authority | Window | Trigger |
|-----------|--------|---------|
| GDPR supervisory authority | 72 hours | Awareness of personal data breach |
| SEC Form 8-K Item 1.05 | 4 business days | Material cybersecurity incident |
| HIPAA individual notice | 60 days | Discovery of breach affecting PHI |
| US state breach laws | 30 to 90 days varies | Discovery of breach affecting state residents |
| Brazil ANPD | Reasonable, ANPD treats as 2 business days | Discovery |
| NIS2 essential entities | Early warning 24h, incident notification 72h | Significant incident |

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| Storing access tokens in `localStorage` | XSS vulnerability |
| Storing JWT refresh tokens in any client-side storage other than httpOnly cookies | Token theft via XSS |
| `unsafe-inline` or `unsafe-eval` in CSP | Defeats CSP purpose |
| `Set-Cookie` without `Secure` and `HttpOnly` for session cookies | Token theft via JS or unencrypted transport |
| TLS 1.0 or 1.1 endpoints | Cryptographically broken |
| MD5 or SHA-1 for password hashing | Fast hashes, not password hashes |
| `eval()`, `new Function(...)`, or `setTimeout(string, ...)` | Code execution |
| Regex with unbounded backtracking on user input | ReDoS |
| HTML-string injection via `innerHTML` with user data | XSS |
| Open redirect to user-supplied URL | Phishing |

## Mechanical Enforcement

Existing hooks under [`../hooks/`](../hooks) provide secret scanning, dangerous command blocking, token guards, internal config leakage, force-push during review. No new cybersecurity hook in this rule; existing coverage is sufficient at the development surface.

## Cross-References

- [`security.md`](security.md): cross-cutting security baseline
- [`compliance-defaults.md`](compliance-defaults.md): umbrella rule
- [`../standards/cybersecurity-baseline.md`](../standards/cybersecurity-baseline.md): breach notification UI templates, NIS2 + DORA scope
- [`../standards/secrets-management.md`](../standards/secrets-management.md): secrets handling
- [`privacy-defaults.md`](privacy-defaults.md): privacy obligations overlap

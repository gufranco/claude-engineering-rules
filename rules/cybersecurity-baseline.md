# Cybersecurity Baseline

Applies to every frontend task, alongside [`security.md`](security.md).

- TLS 1.3 for new endpoints, HTTPS only, HSTS preload with a 2-year max-age.
- Session cookies are `HttpOnly`, `Secure`, `SameSite=Lax` or stricter; never tokens in `localStorage`.
- Nonce CSP with `strict-dynamic`, never `unsafe-inline` or `unsafe-eval`; `integrity` on external scripts.
- Session timeout 15 min sensitive, 60 min otherwise; never redirect to a user-supplied URL.

Full rule, examples, and rationale: [`standards/cybersecurity-defaults.md`](../standards/cybersecurity-defaults.md). Read it before touching auth, headers, or breach handling.

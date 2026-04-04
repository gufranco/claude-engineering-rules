# Authentication

## OAuth 2.1 with PKCE

Use OAuth 2.1 as the authorization framework. PKCE is mandatory for all client types, not just public clients.

- Code challenge method: S256 only. Never allow `plain`.
- Authorization code flow for web and mobile apps. No implicit flow.
- State parameter required on every authorization request to prevent CSRF.
- Redirect URI must be an exact match, no wildcards, no pattern matching.

```typescript
import { randomBytes, createHash } from "node:crypto";

function generatePKCE(): { verifier: string; challenge: string } {
  const verifier = randomBytes(32).toString("base64url");
  const challenge = createHash("sha256")
    .update(verifier)
    .digest("base64url");
  return { verifier, challenge };
}
```

## Access Tokens

| Property | Requirement |
|----------|-------------|
| Format | JWT signed with RS256 |
| Lifetime | 15 minutes maximum |
| Claims | `sub`, `iat`, `exp`, `iss`, `aud`, `jti`, `scope` |
| Storage | Never in localStorage. Use httpOnly secure cookies or in-memory only |
| Validation | Verify signature, expiration, issuer, and audience on every request |

Short-lived tokens limit the blast radius of a compromised token. Pair with refresh token rotation for seamless UX.

## Refresh Token Rotation

Issue a new refresh token on every use. Invalidate the previous one immediately.

- Track refresh tokens by family. A family starts when the user authenticates.
- If a previously used refresh token is presented, revoke the entire family. This detects replay attacks.
- Store refresh tokens hashed, never in plaintext.
- Set an absolute lifetime on refresh token families: 7-30 days depending on risk tolerance.

```typescript
async function rotateRefreshToken(
  currentToken: string,
): Promise<TokenPair> {
  const family = await tokenStore.findFamily(currentToken);

  if (family.isRevoked) {
    await tokenStore.revokeEntireFamily(family.id);
    throw new SecurityError("refresh token replay detected");
  }

  await tokenStore.revokeToken(currentToken);
  const newRefresh = generateRefreshToken(family.id);
  const newAccess = generateAccessToken(family.userId);

  await tokenStore.save(newRefresh);
  return { accessToken: newAccess, refreshToken: newRefresh };
}
```

## Passkeys and FIDO2

Passkeys replace passwords with public-key cryptography. The private key never leaves the user's device.

- Set `userVerification: "required"` in registration and authentication options.
- Validate the authenticator's signature counter on each login. A counter that does not increment may indicate a cloned credential.
- Allow multiple passkeys per user. Users have multiple devices.
- Store the credential public key, credential ID, and counter server-side.
- Support cross-device authentication via CTAP2 hybrid transport.

| Registration field | Value |
|-------------------|-------|
| `rp.id` | Your domain, no scheme, no port |
| `rp.name` | Display name for the relying party |
| `authenticatorSelection.residentKey` | `"required"` for discoverable credentials |
| `authenticatorSelection.userVerification` | `"required"` |
| `attestation` | `"none"` unless you need device attestation |

## Password Policy

Follow NIST 800-63B guidelines. Traditional complexity rules do not improve security and degrade usability.

| Rule | Requirement |
|------|-------------|
| Minimum length | 12 characters |
| Maximum length | 128 characters minimum support |
| Complexity rules | None. No uppercase/lowercase/symbol requirements |
| Forced rotation | None. Change only on evidence of compromise |
| Breach check | Check against HaveIBeenPwned API on registration and change |
| Common passwords | Block the top 100,000 common passwords |
| Hashing | argon2id with recommended parameters, or bcrypt with cost 12+ |
| Truncation | Never truncate or limit the password before hashing |

## Multi-Factor Authentication

Offer MFA as opt-in for all users. Require it for admin roles.

| Method | Security level | UX impact |
|--------|---------------|-----------|
| Passkey | Highest, phishing-resistant | Lowest friction |
| TOTP app | High | Medium friction |
| SMS OTP | Moderate, vulnerable to SIM swap | Medium friction |
| Email OTP | Moderate | Higher friction |

- TOTP: generate a 160-bit secret, encode as base32, display as QR code. Validate with a 30-second window and one step of tolerance.
- Recovery codes: generate 10 single-use codes at MFA enrollment. Hash and store them. Each code is consumed on use.
- Never fall back to a weaker method if a stronger one is enrolled.

## Session Management

- Generate session IDs with a cryptographically secure random generator. Minimum 128 bits of entropy.
- Regenerate the session ID after authentication to prevent session fixation.
- Set idle timeout: 30 minutes for standard apps, 5 minutes for sensitive operations.
- Set absolute timeout: 12 hours regardless of activity.
- Invalidate all sessions on password change.
- Store sessions server-side. The session cookie contains only the session ID.

| Cookie attribute | Value |
|-----------------|-------|
| `HttpOnly` | `true` |
| `Secure` | `true` |
| `SameSite` | `Lax` or `Strict` |
| `Path` | `/` or the narrowest applicable path |
| `Domain` | Omit to default to the exact origin |

## Rate Limits for Auth Endpoints

Aggressive rate limiting on authentication endpoints prevents credential stuffing and brute force attacks.

| Endpoint | Limit | Lockout |
|----------|-------|---------|
| Login | 5 failed attempts per account | 15-minute lockout, notify user |
| Password reset request | 3 per email per hour | Silent rate limit, always return 200 |
| MFA verification | 5 attempts per session | Invalidate session, require re-authentication |
| Account creation | 3 per IP per hour | CAPTCHA challenge after limit |
| Token refresh | 10 per minute per user | Revoke token family on excess |

Use a sliding window counter, not a fixed window. Fixed windows allow burst attacks at window boundaries.

Return `429 Too Many Requests` with a `Retry-After` header. Never reveal whether an account exists through rate limit responses. The response shape and timing must be identical for existing and non-existing accounts.

## Related Standards

- `standards/secrets-management.md`: Secrets Management
- `standards/api-design.md`: API Design
- `standards/privacy-engineering.md`: Privacy Engineering

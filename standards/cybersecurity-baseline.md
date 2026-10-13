# Cybersecurity Baseline (Frontend)

## Disclaimer

This standard summarizes the obligations of NIS2 Directive 2022/2555, DORA Regulation 2022/2554, US SEC Cybersecurity Disclosure Rule (Dec 2023), US state breach notification statutes, GDPR Art. 32-34, LGPD Art. 46-48, and HIPAA Privacy + Security Rules. It is a technical default, not legal advice.

## Breach Notification Timeline Matrix

| Authority | Window | Trigger event | UI obligation |
|-----------|--------|---------------|---------------|
| GDPR supervisory authority | 72 hours | Awareness of personal data breach | Notification to authority |
| GDPR affected data subjects | "Without undue delay" when high risk | Same as above | User-facing notification |
| SEC Form 8-K Item 1.05 | 4 business days | Material cybersecurity incident determination | 8-K filing |
| HIPAA individual notice | 60 days | Discovery of breach affecting PHI | Letter + posting |
| HIPAA media notice (500+ residents in state/jurisdiction) | 60 days | Same | Media outlets |
| HIPAA HHS notice | 60 days (500+) or annual (<500) | Same | HHS portal |
| US state breach laws | 30 to 90 days varies | Discovery of breach affecting state residents | User-facing notification |
| NIS2 essential entities early warning | 24 hours | Significant incident | Authority |
| NIS2 incident notification | 72 hours | Same | Authority |
| NIS2 final report | 1 month | Same | Authority |
| Brazil ANPD | ~2 business days (ANPD interpretation) | Discovery of incident | Authority + affected users |
| Brazil affected data subjects | "Reasonable time" | Same | User-facing notification |

## Breach Notification UI Template

User-facing breach notice (after first establishing the legal obligation to notify):

```
Subject: Security incident affecting your account

We are writing to inform you of a security incident detected on
[DATE]. Based on our investigation, [TYPES OF DATA] of your
account may have been affected.

What happened: [BRIEF DESCRIPTION]
When: [DATE/TIME RANGE]
What we are doing: [REMEDIATION STEPS]
What you should do:
  - [SPECIFIC USER ACTIONS]
  - Change your password if you reused it elsewhere

For more information, contact [SUPPORT CHANNEL].
For details on this incident, visit [STATUS PAGE URL].
```

Localize per supported language, per the locale equivalence target in [`compliance-defaults.md`](compliance-defaults.md).

## NIS2 Scope (EU Directive 2022/2555)

Applies to essential and important entities across 18 sectors including energy, transport, banking, financial markets, health, drinking water, wastewater, digital infrastructure, ICT service management, public administration, space, postal, waste management, chemicals, food, manufacturing of certain products, digital providers, research.

Frontend implications:
- Incident reporting UI for internal staff
- Public status page with incident history
- Notification mechanism for affected users + business partners
- Supply chain attestation (vendor list, dependencies)

## DORA Scope (EU Regulation 2022/2554)

Applies to financial entities (credit institutions, investment firms, payment institutions, e-money, crypto-asset service providers) and their ICT third-party providers.

Frontend implications:
- ICT risk register accessible to authorized roles
- Incident classification UI
- Resilience testing artifacts
- Sub-processor / third-party provider disclosure

## Security Headers (Required)

Full table in [`../rules/security.md`](../rules/security.md). Summary:

| Header | Value |
|--------|-------|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` |
| `Content-Security-Policy` | Nonce-based per template in security.md |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` (legacy; superseded by CSP frame-ancestors) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Disable unused APIs |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `Cross-Origin-Embedder-Policy` | `require-corp` |
| `Cross-Origin-Resource-Policy` | `same-site` or `same-origin` |

## Session Management Defaults

| Parameter | Sensitive flow | Non-sensitive flow |
|-----------|---------------|-------------------|
| Idle timeout | 15 min | 60 min |
| Absolute timeout | 12 h | 24 h |
| Warning before timeout | 20 s | 60 s |
| Extension mechanism | One-click | One-click |
| Cookie flags | HttpOnly, Secure, SameSite=Strict, `__Host-` prefix | HttpOnly, Secure, SameSite=Lax |
| Re-auth on sensitive actions | Required | Optional |

## MFA Implementation

Per [`authentication.md`](authentication.md). Mandatory for any account touching personal, payment, health, or admin data.

Preferred methods:
1. Passkey (WebAuthn) - phishing-resistant
2. TOTP (RFC 6238)
3. Hardware token (FIDO U2F / FIDO2)
4. SMS (last resort; SIM-swap vulnerable)

## Sub-Resource Integrity

Every external `<script>` and `<link rel="stylesheet">` includes an `integrity` attribute with the SHA-384 hash:

```html
<script src="https://cdn.example.com/lib.js"
        integrity="sha384-..."
        crossorigin="anonymous"></script>
```

Build pipeline regenerates the hash on every dependency upgrade.

## Open Redirect Prevention

```typescript
const ALLOWED_REDIRECTS = ["/dashboard", "/profile", "/orders"];

function isAbsoluteUrl(target: string): boolean {
  return target.startsWith("//") || target.includes("://");
}

function safeRedirect(target: string): string {
  if (isAbsoluteUrl(target)) {
    return "/";
  }
  return ALLOWED_REDIRECTS.find((p) => target.startsWith(p)) ?? "/";
}
```

## SSRF Prevention (Server-Side Fetch on Behalf of Frontend)

```typescript
import { BlockList, isIP } from "node:net";

type Subnet = readonly [network: string, prefix: number];

const BLOCKED_IPV4: readonly Subnet[] = [
  ["0.0.0.0", 8], ["10.0.0.0", 8], ["100.64.0.0", 10], ["127.0.0.0", 8],
  ["169.254.0.0", 16], ["172.16.0.0", 12], ["192.0.0.0", 24],
  ["192.168.0.0", 16], ["198.18.0.0", 15], ["224.0.0.0", 4], ["240.0.0.0", 4],
];

const BLOCKED_IPV6: readonly Subnet[] = [
  ["::", 128], ["::1", 128], ["64:ff9b::", 96], ["2002::", 16],
  ["fc00::", 7], ["fe80::", 10], ["ff00::", 8],
];

function buildBlockList(): BlockList {
  const list = new BlockList();
  BLOCKED_IPV4.forEach(([network, prefix]) => list.addSubnet(network, prefix, "ipv4"));
  BLOCKED_IPV6.forEach(([network, prefix]) => list.addSubnet(network, prefix, "ipv6"));
  return list;
}

function isPublicAddress(ip: string, blocked: BlockList): boolean {
  const family = isIP(ip);
  if (family === 0) {
    return false;
  }
  return !blocked.check(ip, family === 4 ? "ipv4" : "ipv6");
}
```

Build the list once at startup and pass it in. `BlockList` parses the address, so it catches the forms a prefix regex misses: `::ffff:169.254.169.254` and `::ffff:a9fe:a9fe` match the IPv4 rules, and `fe80:0:0::1`, `FE80::1`, and `fd12::1` match the IPv6 rules. Input that is not an IP literal fails closed.

Resolve the URL first, validate every resolved IP, then fetch by that IP. Re-validate on every redirect to prevent DNS rebinding.

## Maintenance

Review this standard:

- When NIS2 implementing acts are adopted (Member State transpositions, technical specifications)
- When DORA RTS/ITS are published by ESAs
- When SEC issues amendments to the Cybersecurity Disclosure Rule
- When NIST 800-63 revisions appear
- When a new US state passes a breach notification law
- Yearly review on 1 January

## Related Standards

- [`../rules/cybersecurity-baseline.md`](../rules/cybersecurity-baseline.md)
- [`../rules/security.md`](../rules/security.md): cross-cutting security baseline including full headers table, CSP template
- [`authentication.md`](authentication.md): OAuth 2.1, passkeys, NIST 800-63B
- [`secrets-management.md`](secrets-management.md): Vault, External Secrets Operator
- [`observability.md`](observability.md): incident logging

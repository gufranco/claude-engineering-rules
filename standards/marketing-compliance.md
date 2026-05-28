# Marketing and Anti-Spam Compliance

## Disclaimer

This standard summarizes the obligations of US CAN-SPAM Act (15 USC 7701), Canada CASL (SC 2010 c 23), EU GDPR + ePrivacy Directive, UK PECR 2003, Brazil LGPD + CDC. It is a technical default, not legal advice.

## Per-Jurisdiction Consent Matrix

| Jurisdiction | Marketing email | Marketing SMS | Push notification |
|--------------|----------------|--------------|-------------------|
| EU GDPR + ePrivacy | Opt-in (soft opt-in for similar products from existing customer) | Opt-in | Opt-in |
| UK PECR | Opt-in (soft opt-in for similar products) | Opt-in | Opt-in |
| US CAN-SPAM | Opt-out (sender can email; recipient can unsubscribe) | TCPA: opt-in for autodialed | Generally opt-in via app permission |
| Canada CASL | Express opt-in (implied limited to 24 months post-existing-business-relationship) | Express opt-in | Express opt-in |
| Brazil LGPD | Opt-in (soft opt-in for direct marketing of similar products to existing customer with easy opt-out) | Opt-in | Opt-in |

**Locked default**: opt-in everywhere. CAN-SPAM opt-out treated as a floor, not a ceiling. The user's default behavior accepts only what they explicitly subscribed to.

## Opt-in Recording

```typescript
interface MarketingConsent {
  readonly userId: string;
  readonly channel: "email" | "sms" | "push";
  readonly purpose: "newsletter" | "product-updates" | "promotions" | "third-party-offers";
  readonly grantedAt: Date;
  readonly textVersion: string;       // version of consent text
  readonly source: string;             // "registration", "settings", "checkout-checkbox"
  readonly ip: string;
  readonly userAgent: string;
}
```

Each purpose is a separate consent. "Newsletter" does not imply "third-party offers".

## Unsubscribe Mechanism

| Channel | Mechanism |
|---------|-----------|
| Email | `List-Unsubscribe` header (RFC 8058) + visible link in body + one-click landing page |
| SMS | Reply STOP per US TCPA + dedicated keyword per local convention |
| Push | OS-level disable + in-app toggle |
| In-app message | One-tap dismiss + dedicated settings page |

Email `List-Unsubscribe` example:

```
List-Unsubscribe: <mailto:unsubscribe@example.com?subject=unsubscribe>, <https://example.com/unsubscribe?token=...>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```

One-click landing: opening the URL processes the unsubscribe; no login, no confirmation step, no "are you sure?" page.

## Unsubscribe Processing Time

| Jurisdiction | Max time |
|--------------|----------|
| CAN-SPAM | 10 business days |
| EU GDPR | "Without undue delay" (treated as immediate) |
| LGPD | Sem demora injustificada (treated as immediate) |
| CASL | 10 business days |

**Locked default**: process immediately. Stop sending to the address within 1 hour of unsubscribe.

## Identity Disclosure

Every commercial email contains in the footer:

- Sender legal name
- Physical postal address (CAN-SPAM strict requirement)
- Contact email
- Link to privacy policy
- Link to manage preferences
- Reason recipient is receiving the email ("You signed up at example.com on [DATE]")

## Subject Line Rules

- Accurate description of content; no clickbait
- No "Re:" or "Fwd:" abuse to mimic personal correspondence
- No fake personalization tokens (mass mail addressed as if individual)
- No urgency tactics ("URGENT", "FINAL NOTICE") unless genuinely urgent
- No misleading claims

## Transactional vs Marketing Distinction

| Transactional | Marketing |
|---------------|-----------|
| Triggered by user action (order, password reset, account change) | Sender-initiated outreach |
| Primary content is information about the transaction | Primary content is promotion or product info |
| Consent implied by user action | Requires explicit consent |
| Small marketing footer permitted under CAN-SPAM | Full marketing rules apply |

If a "transactional" email contains substantial marketing content (more than ~20% of total content or visual area), it becomes marketing and consent rules apply.

## Suppression List Discipline

```typescript
interface SuppressionEntry {
  readonly identifier: string;          // hashed email, phone, push token
  readonly suppressedAt: Date;
  readonly reason: "unsubscribe" | "bounce" | "complaint" | "manual";
  readonly originalSource: string;       // which list/campaign the unsubscribe came from
}
```

- Permanent. Never delete.
- Apply to every list. Suppression on "newsletter" suppresses to "promotions" by default unless explicitly re-subscribed.
- Re-import: every list refresh re-applies suppression. New imports are checked against the suppression list before any send.

## CASL Express vs Implied Consent

Per CASL (Canada):

| Consent type | When | Window |
|--------------|------|--------|
| Express | Explicit opt-in via form or signed agreement | No expiration; valid until withdrawn |
| Implied (existing business relationship) | Customer purchased within 24 months | 24 months from last purchase |
| Implied (existing non-business relationship) | Donation, volunteer membership within 24 months | 24 months from last contact |
| Implied (inquiry) | Inquiry from prospect within 6 months | 6 months |
| Conspicuous publication | Email publicly available, no statement against unsolicited messages, message relevant to the published context | While address remains published |

Document the basis per recipient. CASL fines start at CAD 1M per violation for businesses.

## Brazil LGPD + CDC Marketing

LGPD Art. 7 lists 10 lawful bases. For marketing, the typical bases are consent (Art. 7-I) or legitimate interest (Art. 7-IX) with balancing test.

Brazil CDC + ANPD Guia Orientativo:

- Soft opt-in permitted for direct marketing of similar products to existing customer with easy opt-out
- Strict opt-in for SMS and WhatsApp marketing
- "Não me chame" registry: must respect Procon "Não me chame" / "Não me ligue" lists
- Clear unsubscribe in every message (Brazilian Portuguese)

## Frequency Limits

When the recipient specifies a frequency preference, respect it. Recommended caps:

| Channel | Default cap | Override |
|---------|-------------|----------|
| Marketing email | 1 per week max | Recipient can request more |
| SMS | 1 per week max | Same |
| Push notification | 1 per day max | Same |
| Transactional email | No cap (action-driven) | n/a |

## Forbidden Patterns

| Pattern | Source |
|---------|--------|
| Pre-checked marketing opt-in box at registration | GDPR + ePrivacy + LGPD + CASL |
| Unsubscribe behind a login | CAN-SPAM + EU |
| Unsubscribe with email-confirmation step | EU + CASL |
| Generic unsubscribe ("Stop all email") that does not respect granular preferences | GDPR + LGPD |
| Adding marketing content to a transactional email beyond a small footer | CAN-SPAM + EU |
| Spoofed From or Reply-To | CAN-SPAM |
| Missing physical postal address in footer | CAN-SPAM |
| Re-emailing unsubscribed addresses after database refresh | Suppression list violation |
| Buying lists from third-party brokers | GDPR + LGPD + CASL |

## Maintenance

Review this standard:

- When FTC updates CAN-SPAM Rule
- When CRTC publishes new CASL interpretation
- When the EU ePrivacy Regulation is adopted
- When Brazil ANPD publishes marketing guidance under LGPD
- When PROCON or Senacon publishes consumer-marketing rules
- Yearly review on 1 January

## Related Standards

- [`../rules/anti-spam-defaults.md`](../rules/anti-spam-defaults.md)
- [`privacy-engineering.md`](privacy-engineering.md): consent recording aligns with privacy rules
- [`cookies-eprivacy.md`](cookies-eprivacy.md): tracking pixels in marketing email require cookie consent
- [`consumer-protection.md`](consumer-protection.md): e-commerce notice obligations overlap

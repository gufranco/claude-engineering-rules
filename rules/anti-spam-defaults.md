# Anti-Spam and Marketing Defaults

## Scope

Loaded on-demand when a frontend task sends, schedules, or queues any electronic communication (email, SMS, push notification, in-app message) for marketing, transactional, or hybrid purposes. Triggered by keywords: email, newsletter, marketing, unsubscribe, spam, CAN-SPAM, CASL, transactional, push notification, broadcast. Per [`compliance-defaults.md`](compliance-defaults.md).

## Mandatory Targets

| Target | Rule |
|--------|------|
| Marketing consent | Opt-in everywhere (GDPR + ePrivacy + LGPD + CASL standard); CAN-SPAM opt-out grandfathered only for existing US-only lists |
| Unsubscribe | One-click unsubscribe; effective within 10 business days max (CAN-SPAM ceiling); GDPR demands "without undue delay" so process immediately |
| List-Unsubscribe header | Required on every marketing email per RFC 8058 |
| Identity disclosure | Sender legal name + physical postal address visible in every commercial email |
| Subject lines | Accurate; no deception; no "Re:" or "Fwd:" abuse |
| Transactional vs marketing | Strict separation: transactional is triggered by user action and contains primarily transactional content; promotional content in transactional email triggers marketing rules |
| Suppression list | Permanent; never email unsubscribed addresses again; do not re-import after data refresh |
| Consent records | Per recipient: opt-in source, timestamp, IP, consent text version |
| Frequency cap | Respect recipient-specified frequency where applicable |
| Brazil LGPD soft opt-in for similar products | Only with prior business relationship and clear opt-out path |
| CASL express vs implied consent | Express required for most cases; implied limited to existing business relationship up to 24 months |

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| Pre-checked marketing opt-in box at registration | GDPR + ePrivacy + LGPD + CASL fail |
| Unsubscribe behind a login | Per CAN-SPAM + EU practice: one-click without login |
| Unsubscribe requiring email confirmation step | Discourages withdrawal; treated as failed compliance |
| Unsubscribe link that says "If you do not wish to receive any email click here" instead of clearly marketing-only | Deceptive; CAN-SPAM violation |
| Sending to addresses obtained via list rental without explicit opt-in | GDPR + LGPD + CASL fail |
| Adding marketing content to a transactional email beyond a small footer | Triggers marketing rules; consent applies |
| Spoofed From/Reply-To address | CAN-SPAM violation |
| No physical postal address in commercial email footer | CAN-SPAM violation |
| Re-emailing unsubscribed addresses after database refresh or re-import | Suppression list violation |

## Cross-References

- [`compliance-defaults.md`](compliance-defaults.md): umbrella rule
- [`../standards/marketing-compliance.md`](../standards/marketing-compliance.md): full implementation guide with opt-in vs opt-out per jurisdiction matrix, consent record template, soft opt-in conditions
- [`privacy-defaults.md`](privacy-defaults.md): consent recording aligns with privacy rules
- [`cookie-discipline.md`](cookie-discipline.md): tracking pixels in marketing email require cookie consent

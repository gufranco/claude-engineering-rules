# Compliance Defaults

## Master Policy Locks

Two policies bind every line of frontend code produced from `~/.claude`:

1. **Strictest applicable rule wins.** When two valid compliance rules conflict, the stricter is applied. No exception for "this jurisdiction permits the laxer rule".
2. **Existing rules are respected even when not yet mandatory.** A rule that exists as a published standard, regulation, or law is treated as if it were in force, regardless of effective date or whether the project's current jurisdictions enforce it. Future-proofing compliance is cheaper than retrofitting after a violation.

These two policies apply by default to every UI task. They override any project-level convention that would lower the bar.

## Ten Compliance Domains

| Domain | Rule | Standard |
|--------|------|----------|
| Accessibility | [`accessibility-defaults.md`](accessibility-defaults.md) | [`../standards/accessibility-testing.md`](../standards/accessibility-testing.md) |
| Privacy and data protection | [`privacy-defaults.md`](privacy-defaults.md) | [`../standards/privacy-engineering.md`](../standards/privacy-engineering.md) + [`../standards/privacy.md`](../standards/privacy.md) |
| Cookies and ePrivacy | [`cookie-discipline.md`](cookie-discipline.md) | [`../standards/cookies-eprivacy.md`](../standards/cookies-eprivacy.md) |
| Cybersecurity baseline | [`cybersecurity-baseline.md`](cybersecurity-baseline.md) | [`../standards/cybersecurity-baseline.md`](../standards/cybersecurity-baseline.md) + [`security.md`](security.md) |
| Consumer protection and e-commerce | [`consumer-defaults.md`](consumer-defaults.md) | [`../standards/consumer-protection.md`](../standards/consumer-protection.md) |
| Children's online privacy | [`children-privacy-defaults.md`](children-privacy-defaults.md) | [`../standards/children-privacy.md`](../standards/children-privacy.md) |
| AI compliance | [`ai-compliance-defaults.md`](ai-compliance-defaults.md) | [`../standards/ai-compliance.md`](../standards/ai-compliance.md) |
| Anti-spam and marketing | [`anti-spam-defaults.md`](anti-spam-defaults.md) | [`../standards/marketing-compliance.md`](../standards/marketing-compliance.md) |
| Sectoral (health, financial, biometric, identity, crypto, tax, whistleblower) | n/a (load standard on-demand by sector keyword) | [`../standards/sectoral-compliance.md`](../standards/sectoral-compliance.md) |
| Topical (DSA, FOIA/LAI, open data, election, content moderation, geolocation) | n/a (load standard on-demand by topical keyword) | [`../standards/topical-compliance.md`](../standards/topical-compliance.md) |

## Default-Loaded Set

For any frontend task, the resolver loads the umbrella rule plus these five always-on domains: accessibility, privacy, cookies, cybersecurity, consumer.

The remaining five domains load on keyword match. Triggers in [`index.yml`](index.yml).

| Domain | Trigger keywords |
|--------|-----------------|
| Children | child, children, kid, minor, under-18, under-16, under-13, COPPA, AADC, parental consent, age gate |
| AI | ai, llm, chatbot, recommender, generative, gpt, claude, anthropic, openai, deepfake, automated decision, model output |
| Anti-spam | email, newsletter, marketing, unsubscribe, spam, CAN-SPAM, CASL, transactional |
| Sectoral | hipaa, phi, health, medical, pci, payment, card, biometric, fingerprint, face, kyc, aml, identity, crypto, blockchain, vat, tax, whistleblower |
| Topical | dsa, content moderation, transparency, foia, lai, open data, election, political ad, geolocation |

## Cross-Cutting Targets (Locked)

The full conflict catalog lives in the spec folder. Locked targets that every frontend task applies by default:

| Decision | Locked target |
|----------|---------------|
| WCAG version | 2.2 AA mandatory + 2.2 AAA where it does not conflict with AA |
| Older WCAG criteria removed in newer versions (e.g., 4.1.1 Parsing) | Keep meeting them |
| Accessibility statement | Required on every project |
| Authentication | Passkey or OAuth or magic link; no image CAPTCHA |
| Target size | 44x44 CSS pixels (AAA + Apple HIG), 48x48 on Android |
| Color contrast | Aim AAA 7:1, AA 4.5:1 is the floor |
| Sign language for video | Provided where signing community exists for the locale |
| Locale equivalence | Every accessibility feature implemented per language |
| Mobile apps | Same WCAG 2.2 AA + EN 301 549 mobile clauses |
| Reduced motion | prefers-reduced-motion always honored |
| Time limits | Always user-adjustable within security envelope |
| Deadlines | Treated as already passed |
| Privacy consent | Opt-in by default everywhere |
| Children threshold | 18 for profiling/ads; 16 for accounts; 13 minimum with verifiable parental consent under 13 |
| Breach notification | 72 hours external + 4 business days SEC for reporting entities |
| Data retention default | 24 months operational; longer only with explicit legal hold |
| International data transfers | SCCs or BCRs or adequacy by default; multi-region with EU data primary in EU |
| Pseudonymous data | Treated as personal data |
| Password policy | NIST 12-char no-complexity-no-rotation + MFA for sensitive |
| Session timeout | 15 min sensitive, 60 min non-sensitive, with warning + extension |
| Withdrawal period | 14 days for distance-sale contracts |
| AI disclosure | Visible label on every model-produced surface |
| AI bias audit | Annual for any automated decision system |
| Geolocation | Treated as sensitive everywhere |

## Disclaimer

The compliance standards are technical defaults aligned with the laws referenced. They are not legal advice. A project owner consults counsel for jurisdiction-specific application.

## Cross-References

- [`security.md`](security.md): cybersecurity baseline (web headers, CSP, encryption, supply chain)
- [`../standards/accessibility-testing.md`](../standards/accessibility-testing.md): accessibility testing infrastructure
- [`../checklists/checklist.md`](../checklists/checklist.md): per-category verification items
- Per-domain rule files listed in the table above

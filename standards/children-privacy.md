# Children's Online Privacy

## Disclaimer

This standard summarizes the obligations of US COPPA (15 USC 6501) + FTC Rule, EU GDPR Article 8, UK Age Appropriate Design Code (Children's Code, 2020), California AADC (AB-2273, 2024), LGPD Article 14 + Decreto 9.094, Brazil ECA (Lei 8.069/1990), Argentina Ley 26.061, and Quebec Law 25 child provisions. It is a technical default, not legal advice.

## Age Threshold Matrix

| Jurisdiction | Parental consent under | Default privacy under |
|--------------|------------------------|----------------------|
| US COPPA | 13 | 13 (verifiable parental consent) |
| EU GDPR Art. 8 default | 16 | 16 |
| Belgium, Italy, Netherlands, Portugal, Spain (14), Czechia, Finland, France (15), Sweden, etc. | varies (member state opt-in to lower, max 13) | per state |
| Germany, Austria, Hungary, Slovakia, Norway, Iceland | 16 | 16 |
| UK Children's Code | 13 (with verifiable parental consent under) | 18 (highest privacy default) |
| California AADC | n/a | 18 (highest privacy default) |
| LGPD Art. 14 | 12 (full parental consent, "criança") | 18 ("adolescente" treated with best-interest test) |
| Brazil ECA | 18 (legal minor; protection extends) | 18 |
| Quebec Law 25 | 14 | 14 |

**Locked defaults per the strictest-wins policy:**
- Profiling and behavioral advertising: **18**
- Account creation: **16**
- Verifiable parental consent threshold: **13**

## High-Privacy Default for Under-18

Per UK Children's Code + California AADC:

```typescript
const DEFAULT_SETTINGS_UNDER_18 = {
  behavioralProfiling: false,
  targetedAdvertising: false,
  geolocationCollection: false,
  geolocationVisibility: false,
  profilePublic: false,
  searchableByOthers: false,
  directMessagesFromStrangers: false,
  contactImport: false,
  reactiveNotifications: false,  // no streaks, no "active now"
  facialRecognition: false,
  emotionRecognition: false,
} as const;
```

Settings cannot be relaxed by the child without an age-appropriate explanation. Parental consent may be required to relax some settings depending on jurisdiction.

## Age Estimation Strategy

Per UK Code: proportional to risk. Avoid mandatory ID upload (data minimization).

Tiers from lightest to strictest:

1. Self-declared age at signup (lowest risk products)
2. Behavioral signals: typing speed, content interaction patterns, time-of-day usage, account age (recommend age-appropriate UI)
3. Email-based parental consent flow (per COPPA-acceptable methods)
4. Government ID upload (last resort, high-risk products only: gambling, alcohol, banking)
5. Credit card verification (US COPPA acceptable method) - only with deletion of card data after verification

## Verifiable Parental Consent (COPPA-acceptable methods)

Per FTC COPPA Rule 16 CFR 312.5:

1. Sign-and-return form (mail, fax, electronic with digital signature)
2. Credit, debit, or other online payment with notification to account holder
3. Toll-free telephone call to trained personnel
4. Video call with trained personnel
5. Government-issued ID verification + deletion of the document
6. Knowledge-based authentication
7. Facial recognition match to government-issued photo ID (FTC-approved 2023)

Pick a method proportional to the data risk. Document which method was used per consent.

## Parental Consent UI Flow

```tsx
function ChildSignupFlow() {
  const [step, setStep] = useState<"age" | "parental" | "settings">("age");

  return match(step)
    .with("age", () => <AgeGate onAgeKnown={handleAgeKnown} />)
    .with("parental", () => <VerifiableParentalConsent />)
    .with("settings", () => <ChildAccountSettings defaults={DEFAULT_SETTINGS_UNDER_18} />)
    .exhaustive();
}
```

After parental consent, all defaults from `DEFAULT_SETTINGS_UNDER_18` apply. Cannot bypass.

## Age-Appropriate UI

Per UK Code:

- Reading level matched to estimated age (Flesch-Kincaid grade <= age - 4 for under-13)
- Plain language explanations of data uses
- No dark patterns (urgency, scarcity, sunk-cost framing)
- No nudge techniques that lower privacy
- No streak counts, no "people online now", no "you have a message from..." that creates urgency
- Time-of-day prompts to take a break for users under 18

## Parental Controls Dashboard

Required when the platform serves users under 18 with parental consent:

- View child's data collection summary
- Adjust child's privacy settings (within the bounded defaults)
- Withdraw consent (deletes account or anonymizes)
- View access log of child's data
- Receive notifications of significant activity (terms changes, breach, suspicious access)

## UK Children's Code: 15 Standards Summary

1. Best interests of the child
2. Data protection impact assessments
3. Age-appropriate application
4. Transparency
5. Detrimental use of data
6. Policies and community standards
7. Default settings (high privacy)
8. Data minimization
9. Data sharing
10. Geolocation
11. Parental controls
12. Profiling
13. Nudge techniques
14. Connected toys and devices
15. Online tools

See [ICO Children's Code guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/) for full text.

## Brazil LGPD Article 14 Specifics

Per ANPD guidance:

- **Child (under 12)**: processing requires specific, prominent parental consent. Best-interest test always applies.
- **Adolescent (12-17)**: processing must serve their best interest. Game-of-chance, adult content, profiling for advertising prohibited.

Quote (translated): "O tratamento de dados pessoais de crianças e adolescentes deverá ser realizado em seu melhor interesse" (LGPD Art. 14). The "best interest" standard is broader than European parental consent.

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| Behavioral advertising to users under 18 | UK Code + California AADC |
| Default privacy "public" for under-18 | UK Code privacy by default |
| Streak counts, "active now", read receipts on by default for under-18 | UK Code nudge-techniques ban |
| Geolocation tracking on by default for under-18 | UK Code |
| Real-time location visibility to other users under-18 | UK Code |
| DM from strangers to under-18 by default | UK Code |
| Mandatory ID upload as age verification | Data minimization fails when behavioral estimation suffices |
| Sign-up flow without an age field for child-likely services | COPPA + AADC fail |
| Skipping verifiable parental consent under 13 | COPPA per-violation civil penalty |
| Reusing the same data for child users that you use for adults | Children's Code + AADC fail |
| Sharing child data with third-party advertisers | COPPA + GDPR + LGPD + UK Code |

## Maintenance

Review this standard:

- When FTC publishes COPPA Rule amendments (notable 2024 NPRM still pending)
- When ICO updates the Children's Code or publishes new guidance
- When California AADC litigation produces appellate rulings
- When EU member states adjust GDPR Art. 8 age thresholds
- When ANPD publishes children's data guidance under LGPD Art. 14
- Yearly review on 1 January

## Related Standards

- [`../rules/children-privacy-defaults.md`](../rules/children-privacy-defaults.md)
- [`privacy-engineering.md`](privacy-engineering.md): broader privacy obligations
- [`accessibility-testing.md`](accessibility-testing.md): age-appropriate UI accessibility
- [`ai-compliance.md`](ai-compliance.md): no profiling under 18; no emotion recognition in education

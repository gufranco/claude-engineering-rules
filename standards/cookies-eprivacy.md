# Cookies and ePrivacy

## Disclaimer

This standard summarizes obligations from the ePrivacy Directive 2002/58/EC, EDPB Guidelines 03/2022 and 05/2020, CNIL cookie guidelines (March 2021), ICO cookie guidance, Brazil ANPD Guia Orientativo sobre Cookies (2023), and CCPA. It is a technical default aligned with the laws referenced, not legal advice.

## Banner UX Specification

### Layout

The cookie banner is a modal dialog. It traps focus, accepts keyboard input, and is announced to screen readers. Banner content:

- A heading describing the choice ("Cookie preferences", not "We use cookies")
- A short description of categories (essential, analytics, marketing, personalization)
- Three buttons of equal visual weight: "Accept all" / "Reject all" / "Manage preferences"
- A link to the full cookie policy

### Button Equivalence

```tsx
// Bad: reject buried behind a "Manage preferences" intermediate step
<button>Accept all</button>
<a href="#preferences">Manage preferences</a>

// Good: reject as easy as accept
<button>Accept all</button>
<button>Reject all</button>
<button>Manage preferences</button>
```

Per EDPB Guidelines 03/2022, "Reject all" must require the same number of clicks as "Accept all". A two-button banner where one button is small grey text and the other is prominent is a violation.

### Granular Categories

```tsx
const CATEGORIES = [
  { id: "strictly_necessary", label: "Strictly necessary", required: true },
  { id: "functional", label: "Functional", required: false },
  { id: "analytics", label: "Analytics", required: false },
  { id: "marketing", label: "Marketing", required: false },
  { id: "personalization", label: "Personalization", required: false },
  { id: "social", label: "Social media", required: false },
] as const;
```

Each toggle starts unchecked except `strictly_necessary`. Saving without changes records only strictly necessary as accepted.

### Accessibility

Banner is a dialog: `role="dialog"`, `aria-modal="true"`, `aria-labelledby` to the heading, `aria-describedby` to the description. ESC closes (default reject). Focus moves into the dialog on open, traps inside, returns on close. See [`accessibility-testing.md`](accessibility-testing.md) for the dialog focus management pattern.

## Consent Record Schema

```typescript
interface ConsentRecord {
  readonly userId: string;            // or anonymous session token
  readonly timestamp: Date;
  readonly textVersion: string;       // version of the consent text shown
  readonly categories: readonly string[];  // accepted category IDs
  readonly source: "banner" | "settings" | "registration";
  readonly userAgent: string;
  readonly ip: string;                // truncated to /24 or /48 per data minimization
}
```

Store with a TTL aligned to the longest applicable retention window. Update on every change. Never overwrite; keep history.

## Withdrawal Mechanism

A persistent link in the footer ("Cookie preferences") opens the manage dialog on every page. Changes take effect immediately:

```typescript
async function applyConsent(record: ConsentRecord): Promise<void> {
  await saveConsent(record);
  await teardownTrackers(getRevokedCategories(previousConsent, record));
  await initTrackers(getNewlyConsentedCategories(previousConsent, record));
  emit("consent.changed", record);
}
```

`teardownTrackers` removes cookies, clears `localStorage` entries, deregisters event listeners, and disables global analytics objects (e.g., `window.gtag = () => {}`).

## Essential Cookie Definition

Essential = strictly required for the service the user explicitly requested. Examples:

- Session cookie for authenticated user
- CSRF token
- Cart contents during checkout
- Language preference selected by user
- Cookie consent record itself

Non-essential (require consent): analytics, A/B testing, behavioral targeting, personalization not explicitly requested, social embeds, marketing pixels, cross-site tracking.

CNIL and ICO permit a narrow analytics exemption when: first-party only, aggregated, anonymized, no cross-site tracking, no marketing use, easy opt-out. Most analytics deployments do not meet all five and require consent.

## CCPA Do Not Sell or Share Link

Required in the footer of every page for sites in CCPA scope. Linked to a page that allows the user to opt out of "sale" and "sharing" of personal information. One-click opt-out, no account required. See `references.md` CCPA section for scope.

## Forbidden Patterns

| Pattern | Source | Reason |
|---------|--------|--------|
| Pre-ticked consent checkboxes | EDPB 05/2020 | Not an active opt-in |
| Continue-browsing-implies-consent | EDPB | Implied consent banned |
| Cookie walls forcing acceptance for access | EDPB | Conditioning service on consent |
| Accept-all prominent + reject-all buried | EDPB 03/2022 + CNIL | Reject parity fails |
| Banner without keyboard operability | WCAG 2.1.1 | Accessibility fail |
| Setting non-essential cookies before consent | ePrivacy Art. 5(3) | Pre-consent processing |
| Hardcoded analytics IDs without consent guard | ePrivacy | Same as above |

## Per-Jurisdiction Variants

| Region | Specific overlay |
|--------|------------------|
| EU | Full opt-in per ePrivacy + GDPR + EDPB |
| UK | Same as EU + ICO-specific deviation notes (similar in practice) |
| France | CNIL guidance: explicit one-click refuse, analytics exemption narrow |
| Germany | Telekommunikation-Telemedien-Datenschutz-Gesetz (TTDSG, 2021): aligned with EU |
| Italy | Garante: similar to EDPB |
| Brazil | ANPD Guia 2023: opt-in for non-essential, legitimate interest possible for narrow analytics with opt-out |
| California | CCPA + CPRA "Do Not Sell or Share" link required; not strictly opt-in but treated as opt-in by strictest-wins policy |

## Mechanical Enforcement

Hook [`../hooks/privacy-leakage-checks.py`](../hooks/privacy-leakage-checks.py) catches cookies set without a consent gate.

## Maintenance

Review this standard:

- When the ePrivacy Regulation is adopted (replacing the 2002 Directive)
- When EDPB or any EU supervisory authority publishes new cookie guidelines
- When CNIL, ICO, ANPD, AEPD, Garante, DSK publishes new national interpretation
- When CCPA + CPRA amendments change the "Do Not Sell or Share" requirement
- Yearly review on 1 January regardless of triggers

## Related Standards

- [`../rules/cookie-discipline.md`](../rules/cookie-discipline.md)
- [`privacy-engineering.md`](privacy-engineering.md)
- [`accessibility-testing.md`](accessibility-testing.md): banner dialog accessibility

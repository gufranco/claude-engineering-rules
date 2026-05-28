# Cookie Discipline

## Scope

Every frontend task that sets cookies, uses localStorage, sessionStorage, IndexedDB, or any other client-side storage. Loaded by default per [`compliance-defaults.md`](compliance-defaults.md). Strictness target: ePrivacy + GDPR opt-in by default everywhere.

## Mandatory Targets

| Target | Rule |
|--------|------|
| Consent default | Opt-in for every non-essential cookie or tracker; essential-only loads at page load |
| Reject-all parity | "Reject all" requires the same number of clicks as "Accept all" |
| Granularity | Categories: strictly necessary, functional, analytics, marketing, personalization, social. Each independently toggleable |
| No pre-ticked boxes | Every consent checkbox starts unchecked |
| No cookie walls | Access does not require accepting non-essential cookies |
| Withdrawal | One click from any page to manage consent; withdrawal effective immediately |
| Banner accessibility | Treated as a modal dialog: `aria-modal`, focus trap, ESC closes, accessible name, keyboard operable |
| Consent record | Per user: timestamp, version of consent text, categories accepted, source (banner, settings, registration) |
| Essential cookie definition | Strictly required for the service the user requested; analytics is not essential |
| Analytics treatment | Server-side analytics or cookieless analytics preferred; tag-based analytics requires consent |
| CCPA "Do Not Sell or Share" link | Required for any site in CCPA scope; one-click in footer |

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| Setting any non-essential cookie before consent | ePrivacy Art. 5(3) violation |
| "Continue browsing implies acceptance" banners | EDPB rejects implied consent |
| Cookie walls that force consent for access | EDPB cookie walls guidance |
| "Accept all" prominent + "Manage preferences" buried | Reject-all parity fails |
| Pre-ticked checkboxes for any category | EDPB consent guidelines fail |
| Banner without keyboard operability | WCAG 2.1.1 fails on top of ePrivacy |
| Banner that traps focus permanently if user dismisses without consent | UX hostile + WCAG fails |
| Hardcoded Google Analytics, GTM, or third-party tracker IDs without surrounding consent guard | Pre-consent loading |
| Marketing pixels (Facebook, LinkedIn, TikTok) fired before consent | ePrivacy + GDPR fail |
| Storing user IDs in `localStorage` without consent | Same rule as cookies under ePrivacy |

## Mechanical Enforcement

The hook [`../hooks/privacy-leakage-checks.py`](../hooks/privacy-leakage-checks.py) catches:
- `document.cookie =` or `setCookie(` not preceded by a consent check
- `localStorage.setItem(` with identifiable user data
- Hardcoded analytics or marketing tracker IDs without surrounding consent guard

Bypass env: `PRIVACY_CHECKS_DISABLE=1` (parent shell only).

## Implementation Pattern

```typescript
// Bad: loads analytics on page load
import { initAnalytics } from "./analytics";
initAnalytics(); // runs before consent

// Good: gated on consent
import { onConsentChange } from "./consent";
import { initAnalytics, teardownAnalytics } from "./analytics";

onConsentChange((categories) => {
  if (categories.includes("analytics")) {
    initAnalytics();
  } else {
    teardownAnalytics();
  }
});
```

## Cross-References

- [`compliance-defaults.md`](compliance-defaults.md): umbrella rule
- [`privacy-defaults.md`](privacy-defaults.md): privacy obligations
- [`../standards/cookies-eprivacy.md`](../standards/cookies-eprivacy.md): full banner UX patterns and category definitions
- [`accessibility-defaults.md`](accessibility-defaults.md): banner accessibility

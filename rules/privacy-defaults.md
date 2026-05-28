# Privacy Defaults

## Scope

Every frontend task that collects, stores, processes, or displays personal data. Loaded by default per [`compliance-defaults.md`](compliance-defaults.md). Strictness target: GDPR-grade by default everywhere, regardless of the project's stated jurisdiction.

## Mandatory Targets

| Target | Rule |
|--------|------|
| Lawful basis | Every processing activity has a documented lawful basis (consent, contract, legal obligation, vital interest, public task, legitimate interest) |
| Consent | Opt-in, granular, withdrawable as easily as granted; no pre-ticked boxes; no bundled consents |
| DSAR window | 30 days from request to fulfillment |
| Erasure | Truly gone or irreversibly anonymized; soft delete is insufficient |
| Breach notification | 72 hours to supervisory authority (GDPR Art. 33) + 4 business days SEC for reporting entities + 3 business days ANPD per Resolução 15/2024 for LGPD scope |
| Retention default | 24 months operational; longer only with explicit legal hold |
| DPO designation | Every project designates a DPO; LGPD requires one |
| DPIA trigger | Profiling, large-scale sensitive data, systematic monitoring, automated decision-making, new technology, children's data, biometric, geolocation |
| International transfers | SCCs or BCRs or adequacy by default; multi-region with EU data primary in EU |
| Pseudonymous data | Treated as personal data |
| Sensitive data | Union of all definitions: racial/ethnic, political, religious, trade union, genetic, biometric, health, sexual life and orientation, criminal records, financial credentials, geolocation (precise), children's data, immigration status |
| Audit trail | Every personal data access logged with actor, target, timestamp, IP, user agent, reason |
| Automated decision-making | Human review available, plain-language explanation, appeal mechanism |

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| Soft delete with `isDeleted` flag for erasure requests | Data is not gone |
| Bundling consent for multiple purposes in one checkbox | GDPR Art. 7 fails |
| Pre-ticked consent checkboxes | EDPB Guidelines 05/2020 fail |
| "Reject all" requiring more clicks than "Accept all" | Withdrawal not as easy as grant; CNIL guidance fails |
| Storing raw ID documents long-term | Data minimization fails |
| Logging personal data in application logs | Log the identifier, not the value |
| PII in URLs or query parameters | Leaks to referrer, logs, browser history |
| Personal data in error messages | Leaks to logs, tickets, support channels |
| Hashing email as "pseudonymization" | Still personal data; hash is reversible with rainbow tables |
| Copying production personal data to non-production environments | Use Faker-generated synthetic data |
| Treating GDPR opt-out (CCPA model) as the default in any market | Strictest-wins requires opt-in everywhere |

## Mechanical Enforcement

The hook [`../hooks/privacy-leakage-checks.py`](../hooks/privacy-leakage-checks.py) catches PII patterns in console.log, localStorage, cookies without consent gates, and analytics IDs without consent guards. Bypass env: `PRIVACY_CHECKS_DISABLE=1` (parent shell only).

## Audit Workflow

For every frontend change touching personal data:

1. The privacy-auditor agent runs (see [`../agents/privacy-auditor.md`](../agents/privacy-auditor.md)) flagging personal data flows, missing consent gates, retention violations.
2. Data inventory: confirm every personal data field has a documented business justification, retention period, deletion method, and access control.
3. Cross-check: every new field appears in the project's data classification table.

## Cross-References

- [`compliance-defaults.md`](compliance-defaults.md): umbrella rule
- [`../standards/privacy-engineering.md`](../standards/privacy-engineering.md): full implementation guide
- [`../standards/privacy.md`](../standards/privacy.md): condensed reference
- [`security.md`](security.md): security baseline (encryption, audit logs)
- [`cookie-discipline.md`](cookie-discipline.md): cookies and ePrivacy specifics
- [`children-privacy-defaults.md`](children-privacy-defaults.md): children's data

# Privacy Engineering

## Pseudonymization

Separate identifying attributes from behavioral and transactional data. The two datasets are stored independently and linked only through a key held in a separate, access-controlled system.

| Data category | Storage | Access |
|-------------|---------|--------|
| Identifiers: name, email, phone, government ID | Identity store with encryption at rest | Restricted to identity service |
| Behavioral: clicks, page views, preferences | Analytics store with pseudonymous user token | Broader team access |
| Transactional: orders, payments, subscriptions | Business store with pseudonymous user token | Service-level access |

- The pseudonymous token is a random, non-reversible identifier. Not a hash of the email or a predictable sequence.
- The mapping between real identity and token lives in the identity store only.
- Deleting the mapping entry pseudonymizes all linked behavioral and transactional data permanently.

```typescript
interface IdentityRecord {
  readonly userId: string;          // pseudonymous token
  readonly email: string;           // real identifier
  readonly name: string;            // real identifier
  readonly createdAt: Date;
  readonly consentVersion: string;
}

interface BehavioralRecord {
  readonly userId: string;          // pseudonymous token only
  readonly action: string;
  readonly metadata: Record<string, unknown>;
  readonly timestamp: Date;
}
```

## Data Retention Automation

Define a retention period for every data category. Automate deletion. Manual deletion processes get skipped.

| Data category | Retention period | Deletion method |
|-------------|-----------------|----------------|
| Session data | 24 hours | TTL in cache layer |
| Access logs | 90 days | Log rotation with automated purge |
| User behavioral data | 12 months | Scheduled job, hard delete or aggregate |
| Account data | Duration of account + 30 days after deletion | Deletion pipeline triggered by account closure |
| Financial records | As required by jurisdiction, typically 5-7 years | Archive, then delete after retention expires |
| Backup data | 30 days | Automated backup expiration |

- Every table or collection that stores personal data must have a `retentionCategory` annotation in the schema.
- A retention enforcement job runs daily, deletes records past their retention period, and logs the count.
- Backups must also respect retention. A backup taken before deletion that is restored after deletion re-introduces deleted data. Set backup TTLs shorter than or equal to the shortest data retention period.

## Right to Erasure

When a user requests deletion, their data must be truly gone or irreversibly anonymized. Soft delete with an `isDeleted` flag does not satisfy erasure requirements.

### Deletion pipeline

1. Receive erasure request. Log the request ID and timestamp, not the user's identity.
2. Identify all data stores containing the user's data.
3. Delete or anonymize in each store.
4. Verify deletion by querying each store.
5. Confirm completion to the user.
6. Delete the erasure request record after confirmation.

```typescript
async function executeErasure(userId: string): Promise<ErasureResult> {
  const stores = registry.getStoresForUser(userId);
  const results: StoreResult[] = [];

  for (const store of stores) {
    const result = await store.eraseUser(userId);
    results.push(result);
  }

  const allSucceeded = results.every((r) => r.success);
  if (!allSucceeded) {
    const failed = results.filter((r) => !r.success);
    await alertOps("erasure-incomplete", { userId, failed });
  }

  return { userId, completedAt: new Date(), stores: results };
}
```

- Target completion within 30 days of the request. Most jurisdictions require this.
- Handle cascade: deleting a user must delete their orders, comments, uploads, and any other owned data.
- Third-party processors: if data was shared with third parties, notify them of the erasure request.

## Consent Management

Record exactly what the user consented to, when, and which version of the consent text they saw.

| Field | Purpose |
|-------|---------|
| `userId` | Who consented |
| `consentType` | What category: marketing, analytics, personalization |
| `consentVersion` | Which version of the consent text was shown |
| `grantedAt` | Timestamp of consent |
| `withdrawnAt` | Timestamp of withdrawal, null if still active |
| `source` | Where consent was collected: registration, settings, banner |

- Consent must be affirmative. Pre-checked boxes do not count.
- Withdrawal must be as easy as granting. If consent was given with one click, withdrawal must be one click.
- Do not bundle unrelated consents. Marketing consent is separate from analytics consent.
- When consent is withdrawn, stop processing the affected data category immediately. Do not wait for a batch job.

## Dark Pattern Avoidance

Consent flows must not manipulate users into granting more access than they intend.

| Dark pattern | Description | Correct alternative |
|-------------|-------------|-------------------|
| Confirm-shaming | "No, I don't want to save money" as the decline option | Neutral language: "Decline" or "No thanks" |
| Hidden decline | Making the reject option visually inferior or hard to find | Equal visual weight for accept and decline |
| Forced consent | Requiring all consents to use the service | Only require consents necessary for the core service |
| Nagging | Repeatedly asking after the user declined | Ask once per version change, respect the answer |
| Pre-selection | Consent checkboxes pre-checked | All checkboxes start unchecked |

## Privacy Impact Assessment

Conduct a PIA before collecting a new category of personal data or using existing data for a new purpose.

### Required questions

1. What data is being collected? List every field.
2. Why is it needed? Map each field to a specific business purpose.
3. Can the purpose be achieved with less data? If yes, collect less.
4. Who will access the data? List roles and services.
5. How long will it be retained? Map to the retention table.
6. Will it be shared with third parties? If yes, document the legal basis.
7. What is the risk if this data is breached? Classify severity.
8. What safeguards are in place? Encryption, access controls, audit logging.

Document the PIA in the project's `docs/privacy/` directory. Reference the PIA in the PR that introduces the data collection.

## Data Subject Access Requests

Respond to DSARs within 30 days. Provide a complete export of all personal data held about the requester.

### Export format

- Machine-readable format: JSON or CSV.
- Include data from all stores: primary database, analytics, logs, backups.
- Clearly label each data category and its source.
- Exclude data about other individuals. If a record references multiple users, redact the others.

### Automation

Build a self-service data export feature. Manual DSAR handling does not scale and introduces human error.

```typescript
async function generateDataExport(userId: string): Promise<DataExport> {
  const stores = registry.getStoresForUser(userId);
  const sections: ExportSection[] = [];

  for (const store of stores) {
    const data = await store.exportUserData(userId);
    sections.push({ source: store.name, category: store.category, data });
  }

  return {
    requestedAt: new Date(),
    userId,
    sections,
    format: "json",
  };
}
```

## Data Classification

Classify all data at creation time. The classification drives encryption, access control, retention, and audit requirements.

| Classification | Examples | Encryption | Access | Retention |
|---------------|----------|-----------|--------|-----------|
| Public | Marketing content, public profiles | Optional | Unrestricted | Indefinite |
| Internal | Business metrics, internal docs | In transit | Employees | Per policy |
| Confidential | Customer data, financial records | At rest + in transit | Role-based | Per regulation |
| Restricted | Passwords, government IDs, health data | At rest + in transit + app-level | Named individuals | Minimum necessary |

Never store restricted data without encryption. Never log confidential or restricted data, even in debug mode.

## Per-Jurisdiction Obligations Matrix

The GDPR-grade default per [`../rules/privacy-defaults.md`](../rules/privacy-defaults.md) covers the union of obligations below. Per-jurisdiction notes for reference:

### GDPR (EU, Regulation 2016/679)

Key articles cited frequently:

| Article | Obligation |
|---------|-----------|
| Art. 5 | Principles: lawfulness, fairness, transparency, purpose limitation, data minimization, accuracy, storage limitation, integrity, accountability |
| Art. 6 | Lawful basis (consent, contract, legal obligation, vital interest, public task, legitimate interest) |
| Art. 7 | Conditions for consent: free, specific, informed, unambiguous, withdrawable |
| Art. 8 | Children's consent age default 16, member states may lower to 13 |
| Art. 9 | Special categories: racial, political, religious, trade union, genetic, biometric, health, sex life, sexual orientation |
| Art. 12-22 | Data subject rights: information, access, rectification, erasure, restriction, portability, objection, ADM |
| Art. 22 | No solely-automated decisions with legal/significant effect without one of: contract necessity, member state law, explicit consent |
| Art. 25 | Privacy by design and by default |
| Art. 28 | Data processor obligations + DPA |
| Art. 32 | Security of processing: pseudonymization, encryption, confidentiality, integrity, availability, resilience |
| Art. 33 | Breach notification to supervisory authority within 72 hours |
| Art. 34 | Breach notification to data subjects when high risk |
| Art. 35 | DPIA when processing is likely to result in high risk |
| Art. 37 | DPO designation: public authority, large-scale systematic monitoring, large-scale special categories |
| Art. 44-49 | International transfers: adequacy decisions, SCCs, BCRs, derogations |

### LGPD (Brazil, Lei 13.709/2018)

Effective 14 August 2018. Articles below verified against the Planalto official text on 2026-05-27.

| Article | Obligation (verified) |
|---------|-----------------------|
| Art. 2 | Disciplina baseada em 7 fundamentos: privacy, informational self-determination, freedom of expression, intimacy, economic development, free competition, human rights |
| Art. 3 | Territorial scope: processing in Brazil, offering products/services to people in Brazil, or data collected in Brazil |
| Art. 5 | Definitions: dado pessoal, dado pessoal sensível (racial/ethnic, religion, political opinion, trade union, religious/philosophical/political org membership, health, sexual life, genetic, biometric when linked to person), dado anonimizado, titular, controlador, operador, encarregado, ANPD |
| Art. 7 | 10 lawful bases including consent, legal obligation, contract, regular exercise of rights in judicial/administrative process, vital interest, health protection, legitimate interest, credit protection |
| Art. 8 | Conditions for consent: written or other manifestation of will; § 1º consent in contract must be in highlighted clause; § 4º consent must be for specific purposes (generic authorizations void); § 5º withdrawal free and facilitated |
| Art. 9 | Right to facilitated access to information about processing |
| Art. 11 | Sensitive data processing requires specific consent or specific lawful basis |
| Art. 14 | "O tratamento de dados pessoais de crianças e de adolescentes deverá ser realizado em seu melhor interesse"; § 1º child data requires specific prominent parental consent; § 3º limited exception for one-time contact; § 4º cannot condition child participation in games/apps on excessive data; § 6º info must be simple, clear, accessible, adapted to child's physical-motor, perceptive, sensory, intellectual, mental characteristics |
| Art. 18 | Data subject rights: confirmation, access, correction, anonymization/blocking/deletion of unnecessary data, portability, elimination of consent-based data, information about shared use, info on consequences of refusal, consent revocation |
| Art. 19 | Confirmation/access response time: immediate (simplified format) or 15 days (complete declaration) |
| Art. 20 | "O titular dos dados tem direito a solicitar a revisão de decisões tomadas unicamente com base em tratamento automatizado de dados pessoais que afetem seus interesses, incluídas as decisões destinadas a definir o seu perfil pessoal, profissional, de consumo e de crédito ou os aspectos de sua personalidade"; § 1º controller must provide clear info on criteria and procedures; § 2º ANPD may audit for discriminatory aspects. (Note: the original "por pessoa natural" clause requiring human review was vetoed via MP 869/2018 then Lei 13.853/2019; current text omits the explicit human-review requirement) |
| Art. 33 | International transfers permitted to: countries with adequate protection per ANPD, with guarantees (SCCs, BCRs), per international cooperation, to protect life, for legal obligation, by ANPD authorization, or specific consent |
| Art. 41 | "O controlador deverá indicar encarregado pelo tratamento de dados pessoais"; § 1º identity + contact must be publicly disclosed; § 2º encarregado activities: receive complaints, receive ANPD communications, orient employees, other tasks; § 3º ANPD may dispense the indication requirement based on size or processing volume (ANPD Resolução CD/ANPD 2/2022 dispenses small processors) |
| Art. 46 | Security measures: technical and administrative measures suitable to protect personal data from unauthorized access and accidental or unlawful destruction, loss, alteration, communication, or any form of inadequate or unlawful processing |
| Art. 48 | "O controlador deverá comunicar à autoridade nacional e ao titular a ocorrência de incidente de segurança que possa acarretar risco ou dano relevante aos titulares"; § 1º notification "em prazo razoável, conforme definido pela autoridade nacional" with minimum: nature of affected data, info about titulares, technical measures, risks, reasons for delay, mitigation. **ANPD Resolução CD/ANPD 15/2024 sets the notification window at 3 business days from awareness.** |
| Art. 50-51 | Best practices and governance, privacy program elements |
| Art. 52-54 | Administrative sanctions: warning, fine up to 2% of revenue capped at R$ 50 million per infraction, daily fine, publicization, blocking, elimination, partial suspension up to 6 months extendable, suspension of processing activity, partial or total prohibition |

### CCPA + CPRA (California)

| Provision | Obligation |
|-----------|------------|
| Notice at collection | Categories of personal info, purposes, sale/share, retention |
| "Do Not Sell or Share" link | Footer of every page in scope |
| Sensitive personal info | Limited use + disclosure right |
| Right to know, delete, correct, portability | Consumer rights |
| Opt-out preference signals | Global Privacy Control (GPC) must be honored |
| Service-provider contracts | Required for processors |

### Other US states (19 omnibus laws)

Common pattern with state-specific variations:

- Right to know, delete, correct, portability
- Opt-out of sale/sharing/targeted advertising
- Opt-in for sensitive data (some states)
- Universal opt-out (some states: CA, CO, CT, OR)
- Data processing agreements

Specifics vary per state. Reference `references.md` for the catalog.

### PIPEDA + Quebec Law 25 (Canada)

| Provision | Obligation |
|-----------|------------|
| 10 Fair Information Principles | Accountability, identifying purposes, consent, limiting collection, limiting use/disclosure/retention, accuracy, safeguards, openness, individual access, challenging compliance |
| Quebec Law 25 | Privacy by default, PIA before any transfer outside Quebec, mandatory DPO, breach record + notification, individual right to data portability |
| Bill 96 overlay | French as the primary service language; locale equivalence applies to privacy notices |

### Conflict Resolution

When two jurisdictions diverge, apply the strictest. Per [`../rules/privacy-defaults.md`](../rules/privacy-defaults.md):

- Consent: opt-in everywhere (GDPR + LGPD + CASL standard)
- Breach window: 72 hours (GDPR) plus 4 business days SEC for reporting entities
- Children age: 18 for profiling, 16 for accounts, 13 minimum with verifiable parental consent
- International transfers: SCCs or BCRs or adequacy by default
- Sensitive data: union of all jurisdictional categories
- DPO: every project designates one (LGPD baseline)
- DPIA: union of trigger criteria

## Related Standards

- [`standards/authentication.md`](authentication.md): Authentication
- [`standards/database.md`](database.md): Database
- [`../rules/privacy-defaults.md`](../rules/privacy-defaults.md): privacy defaults rule
- [`cookies-eprivacy.md`](cookies-eprivacy.md): cookies and ePrivacy implementation
- [`children-privacy.md`](children-privacy.md): children's privacy specifics
- [`ai-compliance.md`](ai-compliance.md): GDPR Art. 22 + LGPD Art. 20 ADM rights

## Maintenance

Review this standard:

- When EDPB or any EU supervisory authority publishes new guidance
- When EU Commission updates SCCs or adequacy decisions
- When ANPD publishes binding LGPD resolutions
- When a new US state passes an omnibus privacy law
- When Canadian Bill C-27 (CPPA) is enacted
- When the ePrivacy Regulation is adopted
- Yearly review on 1 January

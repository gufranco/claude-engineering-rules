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

## Related Standards

- `standards/authentication.md`: Authentication
- `standards/database.md`: Database

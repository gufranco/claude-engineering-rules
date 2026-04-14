# Privacy

## Core Rule

Design for privacy compliance from the start, regardless of current jurisdiction. Retrofitting privacy controls is 10x more expensive than building them in. These rules apply whether the project is subject to GDPR, LGPD, CCPA, or none of them today.

## Data Minimization

Collect only what you need. Every field that stores personal data must have a documented business justification.

| Question | Required answer before adding a field |
|----------|--------------------------------------|
| Why do we need this data? | Specific business function, not "might be useful" |
| How long do we keep it? | Defined retention period with automated deletion |
| Who can access it? | Named roles, not "everyone" |
| What happens if it leaks? | Risk assessment: low, medium, high |

Never store data "just in case." Never collect data before the feature that uses it exists.

## Retention Policies

Every personal data field must have a retention period. Automate deletion after the period expires.

| Data type | Suggested retention | Deletion method |
|-----------|-------------------|-----------------|
| Session tokens | Hours to days | TTL-based expiration |
| Access logs with user IDs | 90 days | Automated purge job |
| Account data | Duration of account + 30 days | Cascade delete on account closure |
| Payment records | As required by tax law, typically 5-7 years | Anonymize after retention, then delete |
| Marketing consent records | Duration of consent + 1 year | Delete after withdrawal processing |

## Right to Erasure

Build a deletion path for every type of personal data from day one. Soft delete is not enough for privacy compliance. The data must be truly gone or irreversibly anonymized.

Requirements:

- A single function or endpoint that deletes all personal data for a given user.
- Deletion must cover: primary database, caches, search indexes, backups within the retention window, log entries, third-party systems that received the data.
- After deletion, the user's identifier must not resolve to any personal data anywhere in the system.
- Test the deletion path regularly. A deletion function that has never been called in production is an untested function.

## Consent Recording

When data use requires consent, record:

| Field | Purpose |
|-------|---------|
| User ID | Who consented |
| Consent type | What was consented to, specific and granular |
| Timestamp | When consent was given, in UTC |
| Consent version | Which version of the terms the user agreed to |
| Collection method | How consent was obtained: checkbox, banner, form |

Make withdrawal easy. The effort to withdraw consent must not exceed the effort to give it.

## Audit Trail

Log every access to personal data with context.

```json
{
  "action": "personal_data_access",
  "userId": "actor-123",
  "targetUserId": "subject-456",
  "dataFields": ["email", "phone"],
  "timestamp": "2026-04-04T12:00:00Z",
  "reason": "support_ticket_789",
  "ip": "192.168.1.1"
}
```

Audit logs themselves must not contain the personal data being accessed. Log the fact of access, not the accessed values.

## Pseudonymization

When analytics, reporting, or testing require user data, pseudonymize it.

- Replace direct identifiers with reversible tokens using a separate key store.
- The mapping between pseudonyms and real identifiers must be stored separately from the pseudonymized data.
- Pseudonymized data is still personal data under GDPR and LGPD. It reduces risk but does not eliminate compliance obligations.
- For test and development environments, use synthetic data generated with Faker. Never copy production personal data to non-production environments.

## Rules

- Every new model that stores personal data must document: what fields are personal, retention period, deletion method, and access controls.
- Encryption at rest for all personal data fields. Use platform-managed keys.
- Never log personal data in application logs. Log identifiers only.
- Never expose personal data in URLs, query parameters, or error messages.
- Review data collection quarterly. Remove fields that are no longer used.

# Secrets Management

## Core Principle

Static secrets in environment variables are a single point of compromise. A leaked `.env` file or a compromised process dumps every secret at once. Dynamic secrets with short TTLs limit the blast radius.

## Dynamic Secrets

Generate secrets on demand with automatic expiration. The application requests a credential, uses it for its TTL, and the system revokes it automatically.

| Tool | Strengths | When to use |
|------|----------|-------------|
| HashiCorp Vault | Mature, broad secret engine support, enterprise features | Multi-cloud, large teams, compliance requirements |
| Infisical | Developer-friendly, open source, good DX | Startups, smaller teams, fast setup |
| OpenBao | Vault fork, fully open source | Teams that want Vault without BSL licensing |
| AWS Secrets Manager | Native AWS integration, automatic rotation | AWS-only workloads |
| GCP Secret Manager | Native GCP integration | GCP-only workloads |

### Database credentials example

Instead of a static database password in an env var, the application requests a short-lived credential from the secrets engine.

```typescript
import { VaultClient } from "./vault";

async function getDatabaseCredentials(): Promise<DatabaseCredentials> {
  const lease = await vault.read("database/creds/app-role");
  // Returns: { username: "v-app-xxxxx", password: "yyyyy", lease_duration: 3600 }

  scheduleRenewal(lease.leaseId, lease.leaseDuration);
  return { username: lease.data.username, password: lease.data.password };
}
```

- Default TTL: 1 hour for database credentials.
- Max TTL: 24 hours. Force credential rotation at least daily.
- Renew before expiration. Schedule renewal at 75% of the TTL.

## External Secrets Operator for Kubernetes

Never store secrets in Kubernetes manifests, Helm values, or CI variables. Use External Secrets Operator to sync secrets from the secrets manager into Kubernetes Secrets at runtime.

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-database
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: app-database-credentials
  data:
    - secretKey: username
      remoteRef:
        key: database/creds/app-role
        property: username
    - secretKey: password
      remoteRef:
        key: database/creds/app-role
        property: password
```

## Static Secrets Policy

Static secrets are acceptable only in local development. Production environments must use dynamic secrets or managed rotation.

| Environment | Static secrets allowed? | Rotation requirement |
|-------------|----------------------|---------------------|
| Local development | Yes, via `.env` files | None |
| CI/CD | Minimize, use OIDC federation where possible | 90 days maximum |
| Staging | No, use secrets manager | Automated |
| Production | No, use secrets manager with dynamic generation | Automated, TTL-based |

## Secret Scanning in CI

Scan every commit for accidentally committed secrets. Block the merge if any are detected.

- Use `truffleHog`, `gitleaks`, or `detect-secrets` in the CI pipeline.
- Scan the full diff, not just the latest commit. Force-pushed branches may contain secrets in earlier commits.
- Pre-commit hooks provide a first line of defense but are bypassable. CI scanning is the mandatory gate.
- Maintain a `.gitleaks.toml` or equivalent allowlist for false positives. Each entry must have a comment explaining why it is safe.

## Rotation Automation

Every secret must have a defined rotation schedule and an automated rotation mechanism.

| Secret type | Rotation frequency | Mechanism |
|-------------|-------------------|-----------|
| Database credentials | Dynamic, 1-hour TTL | Secrets engine generates per-request |
| API keys, internal | 90 days | Automated rotation job |
| API keys, third-party | Per vendor policy | Manual with runbook |
| TLS certificates | 90 days | cert-manager or ACME automation |
| SSH keys | 180 days | Automated rotation with key distribution |
| Encryption keys | Annual | Key versioning, encrypt with latest, decrypt with any |

For key encryption, support multiple active versions. New data is encrypted with the latest key. Decryption tries all active key versions. This allows rotation without re-encrypting all existing data.

## Emergency Revocation Procedure

When a secret is compromised, speed matters more than process. Have a runbook ready.

1. **Revoke immediately.** Disable the compromised credential in the secrets manager or identity provider. Do not wait for investigation.
2. **Assess scope.** Determine which systems used the compromised secret.
3. **Rotate.** Generate new credentials for all affected systems.
4. **Deploy.** Push updated credentials to affected services. Dynamic secrets handle this automatically; static secrets require redeployment.
5. **Audit.** Review access logs for the compromised credential's lifetime. Identify unauthorized access.
6. **Postmortem.** Document how the leak happened and add preventive controls.

Target time from detection to revocation: under 15 minutes. Practice this with tabletop exercises quarterly.

## Environment Isolation

Secrets for different environments must be completely isolated. A staging secret must never grant access to production resources.

| Isolation layer | Requirement |
|----------------|-------------|
| Secret paths | Separate paths per environment: `secret/prod/db`, `secret/staging/db` |
| Access policies | Each environment's service identity can only access its own path |
| Secret stores | Consider separate secret store instances for production |
| Network | Production secrets manager is not reachable from staging networks |
| Audit | Separate audit logs per environment for clear attribution |

## Zero-Trust Secret Access

Authenticate every secret request. Never rely on network location as proof of identity.

- Use workload identity, such as Kubernetes service accounts, IAM roles, or SPIFFE IDs, not shared tokens.
- Bind secrets to specific identities. A secret policy grants access to `service-x` in `namespace-y`, not to "anything in the cluster."
- Log every secret access with the requesting identity, timestamp, and secret path.
- Alert on anomalous access patterns: unusual identities, high-frequency reads, access outside deployment windows.

## Secret Hygiene Checklist

Before every release:

1. No secrets in source code, config files, or container images.
2. `.env.example` documents required variables with placeholder values.
3. CI pipeline includes secret scanning.
4. Production secrets are dynamic or on automated rotation.
5. Emergency revocation runbook is current and tested.
6. Access policies follow least privilege.

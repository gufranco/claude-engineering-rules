# Container Security

## Non-Root Users

Run containers as a non-root user. Container root maps to host root in many configurations. A container escape with root privileges compromises the host.

```dockerfile
# Create a dedicated user in the build stage
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

# Switch to non-root before the entrypoint
USER appuser
```

- Never use `USER root` in the final stage.
- If the application needs to bind to a port below 1024, use `setcap` or configure the container runtime to map the port. Do not run as root for port binding.
- Verify with `docker run --rm <image> whoami`. The output must not be `root`.

## Minimal Base Images

Smaller images have fewer packages, fewer vulnerabilities, and faster pull times.

| Base image | Use case | Approximate size |
|-----------|----------|-----------------|
| `gcr.io/distroless/static` | Go, Rust, statically linked binaries | ~2MB |
| `gcr.io/distroless/cc` | C/C++ with libc | ~20MB |
| `gcr.io/distroless/nodejs` | Node.js applications | ~120MB |
| `alpine:3.x` | When a shell is needed for debugging | ~7MB |
| `ubuntu:24.04` | Only when specific Ubuntu packages are required | ~78MB |

Prefer distroless. It contains no shell, no package manager, and no unnecessary utilities. An attacker who gains code execution in a distroless container has fewer tools available.

## Multi-Stage Builds

Separate the build environment from the runtime environment. Build dependencies, source code, and intermediate artifacts stay out of the final image.

```dockerfile
# Build stage: full toolchain
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Runtime stage: minimal, no build tools
FROM gcr.io/distroless/nodejs22
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
USER 1001
CMD ["dist/main.js"]
```

## No Secrets in Image Layers

Docker image layers are visible to anyone with access to the image. Secrets embedded in any layer persist even if deleted in a later layer.

- Never `COPY .env` or embed API keys, passwords, or certificates in the image.
- Use build-time secrets with `--mount=type=secret` for build-phase access that does not persist in layers.
- Pass runtime secrets through environment variables, mounted volumes, or a secrets manager.

```dockerfile
# Wrong: secret persists in image layer
COPY .env /app/.env

# Correct: build-time secret, not persisted
RUN --mount=type=secret,id=npm_token \
    NPM_TOKEN=$(cat /run/secrets/npm_token) pnpm install
```

## Read-Only Root Filesystem

Mount the container's root filesystem as read-only. Applications write to explicitly defined volumes only.

```yaml
# Kubernetes pod spec
securityContext:
  readOnlyRootFilesystem: true
```

If the application needs to write temporary files, mount `/tmp` as a tmpfs. All persistent writes go through named volumes or external storage.

## Resource Limits

Set CPU and memory limits to prevent a single container from consuming all host resources.

```yaml
# Kubernetes resource specification
resources:
  requests:
    cpu: "250m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "512Mi"
```

| Setting | Guidance |
|---------|----------|
| Memory request | Set to the application's steady-state usage |
| Memory limit | Set to 1.5x-2x the request. OOMKill above this |
| CPU request | Set to the minimum needed for acceptable performance |
| CPU limit | Set to handle burst load. Consider omitting to allow bursting |

- Always set memory limits. An unbounded container can trigger OOMKill on the node, affecting other workloads.
- Monitor actual usage and adjust. Overprovisioning wastes resources. Underprovisioning causes throttling and OOMKills.

## Network Policies

Default Kubernetes networking allows all pod-to-pod traffic. Restrict it.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: app-network-policy
spec:
  podSelector:
    matchLabels:
      app: myapp
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - port: 3000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: database
      ports:
        - port: 5432
```

- Start with deny-all, then add specific allow rules.
- Restrict egress to known destinations. Unrestricted egress enables data exfiltration.
- Test network policies after applying. A misconfigured policy can silently drop legitimate traffic.

## Image Scanning in CI

Scan every image for known vulnerabilities before pushing to the registry.

| Tool | Strengths |
|------|----------|
| Trivy | Fast, broad coverage, supports multiple artifact types |
| Grype | Accurate, integrates with Syft for SBOM |
| Snyk Container | Commercial, tracks fix availability |

```bash
# Scan and fail on critical or high vulnerabilities
trivy image --severity CRITICAL,HIGH --exit-code 1 myapp:latest
```

- Scan in CI before pushing to the registry. Never push unscanned images.
- Scan the registry periodically. New CVEs are published after the image was built.
- Set policy: critical vulnerabilities block deployment. High vulnerabilities require a fix within 7 days.

## SLSA Provenance

Generate build provenance metadata that records how, where, and from what source an image was built.

- Use SLSA Level 2 as a minimum: automated build with signed provenance.
- Level 3 adds build isolation: the build service is hardened and the build cannot be influenced by user-defined parameters beyond the source.
- Attach provenance to the image as an attestation.

## Signed Images with Cosign

Sign container images to verify integrity and origin. Unsigned images in production are a supply chain risk.

```bash
# Sign after building
cosign sign --key cosign.key myregistry/myapp:v1.2.3

# Verify before deploying
cosign verify --key cosign.pub myregistry/myapp:v1.2.3
```

- Store signing keys in a secrets manager, not in the repository.
- Enforce signature verification in the container runtime or admission controller.
- Use keyless signing with Sigstore's Fulcio and Rekor for zero key management overhead.

## Security Context Defaults

Apply security contexts at the pod level for consistent enforcement.

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1001
  runAsGroup: 1001
  fsGroup: 1001
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  seccompProfile:
    type: RuntimeDefault
```

- `allowPrivilegeEscalation: false` prevents `setuid` binaries from gaining root.
- Drop all capabilities, then add back only what is needed.
- `seccompProfile: RuntimeDefault` restricts available syscalls to a safe subset.

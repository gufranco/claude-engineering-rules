# Container Security

Authoritative reference for Dockerfile, Docker Compose, BuildKit, and Kubernetes runtime security. Cross-language. Cross-orchestrator.

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
| `gcr.io/distroless/static` | Go, Rust, statically linked binaries | ~2 MB |
| `gcr.io/distroless/cc` | C/C++ with libc | ~20 MB |
| `gcr.io/distroless/nodejs` | Node.js applications | ~120 MB |
| `cgr.dev/chainguard/<lang>` | Chainguard Images, daily-rebuilt, low-CVE | varies |
| `wolfi-base` | Wolfi linux-undistro for security-critical builds | ~10 MB |
| `alpine:3.x` | When a shell is needed for debugging | ~7 MB |
| `ubuntu:24.04` | Only when specific Ubuntu packages are required | ~78 MB |

Prefer distroless. It contains no shell, no package manager, and no unnecessary utilities. An attacker who gains code execution in a distroless container has fewer tools available. Chainguard Images and Wolfi-based images are valid alternatives when zero-CVE policy is the priority.

## Pin Base Images by Digest

Tags are mutable. A `node:22-alpine` tag can point at a different image tomorrow. Pin by digest so every build resolves to the exact bytes that were last reviewed and scanned.

```dockerfile
FROM node:22-alpine@sha256:8a0b3f4c0c5d... AS builder
```

- Capture the digest with `docker buildx imagetools inspect <image>:<tag> --format '{{.Manifest.Digest}}'` or with `docker pull <image>:<tag> && docker image inspect <image>:<tag> --format '{{index .RepoDigests 0}}'`.
- Update digests as a deliberate change, not as a side effect of `docker pull`.
- Use Dependabot, Renovate, or `docker scout recommendations` to automate digest updates with a PR per bump.
- A tag without a digest is acceptable only in throwaway experiments.

## Multi-Stage Builds

Separate the build environment from the runtime environment. Build dependencies, source code, and intermediate artifacts stay out of the final image.

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-alpine@sha256:8a0b3f4c... AS builder
WORKDIR /app
COPY --link package.json pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    corepack enable && pnpm install --frozen-lockfile
COPY --link . .
RUN pnpm build

# Runtime stage: minimal, no build tools
FROM gcr.io/distroless/nodejs22@sha256:...
WORKDIR /app
COPY --link --from=builder /app/dist ./dist
COPY --link --from=builder /app/node_modules ./node_modules
USER 1001
CMD ["dist/main.js"]
```

- Name every stage. Anonymous stages cannot be referenced by `--target` for partial builds.
- The runtime stage copies only the production artifact. Dev dependencies, build tools, source maps, and test fixtures stay in the builder stage.

## .dockerignore Discipline

The build context is sent to the daemon on every build. Anything not excluded can be `COPY`ed into a layer or leaked into provenance metadata.

| Pattern | Reason |
|---------|--------|
| `.env`, `.env.*` | Secrets |
| `*.pem`, `*.key`, `*.crt`, `*.p12`, `*.pfx` | Keys and certificates |
| `id_rsa*`, `id_ed25519*` | SSH keys |
| `.git/` | History, hooks, possibly credentials in remotes |
| `node_modules/`, `vendor/`, `target/`, `.venv/`, `__pycache__/` | Reinstalled in the build; copying breaks layer cache |
| `.terraform/`, `*.tfstate*` | Infrastructure state and secrets |
| `.idea/`, `.vscode/`, `.fleet/` | IDE configs, sometimes secret tokens |
| `coverage/`, `*.log`, `tmp/` | Build noise |
| `Dockerfile*`, `compose*.yml`, `docker-compose*.yml` | Avoid recursive context inclusion |

Keep the `.dockerignore` file next to the Dockerfile. Without one, every Dockerfile is one accidental `COPY . .` away from leaking secrets into a layer.

## BuildKit Modern Features

BuildKit is the default builder since Docker 23.0. Use its primitives instead of legacy patterns.

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim@sha256:... AS deps
WORKDIR /app

# Cache mount: persists between builds, never lands in a layer
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    pip install --requirement /tmp/requirements.txt

# Build-time secret: visible during the RUN, never persists
RUN --mount=type=secret,id=npm_token,target=/run/secrets/npm_token \
    npm config set //registry.npmjs.org/:_authToken=$(cat /run/secrets/npm_token) && \
    npm ci && \
    npm config delete //registry.npmjs.org/:_authToken

# Heredoc: cleaner than backslash continuation
RUN <<EOF
set -eux
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl
rm -rf /var/lib/apt/lists/*
EOF
```

| Feature | Use |
|---------|-----|
| `# syntax=docker/dockerfile:1` | Pin to the latest stable Dockerfile frontend; required to use modern features |
| `RUN --mount=type=cache,target=<dir>` | Per-stage cache for package managers; survives across builds |
| `RUN --mount=type=bind,source=<file>,target=<path>` | Read files from build context without copying into a layer |
| `RUN --mount=type=secret,id=<name>` | Build-time secrets; never appear in image history |
| `RUN --mount=type=ssh` | SSH agent forwarding for private-repo clones; never persists |
| `COPY --link` | Layer-independent copies; better cache invalidation, faster builds |
| `RUN <<EOF` heredoc | Multi-line scripts without backslash escapes |
| `--target <stage>` | Build only the named stage; CI matrix per stage |

Canonical cache-mount targets:

| Ecosystem | Cache target |
|-----------|-------------|
| Debian / Ubuntu apt | `/var/cache/apt`, `/var/lib/apt` (and disable apt's docker-clean) |
| Alpine apk | `/var/cache/apk` |
| Python pip | `/root/.cache/pip` |
| Node npm | `/root/.npm` |
| Node pnpm | `/root/.local/share/pnpm/store` |
| Node yarn classic | `/usr/local/share/.cache/yarn` |
| Go modules | `/go/pkg/mod` |
| Go build cache | `/root/.cache/go-build` |
| Cargo | `/usr/local/cargo/registry`, `/usr/local/cargo/git` |
| Maven | `/root/.m2/repository` |
| Gradle | `/root/.gradle/caches` |

## No Secrets in Image Layers

Docker image layers are visible to anyone with access to the image. Secrets embedded in any layer persist even if deleted in a later layer.

- Never `COPY .env`. Never bake API keys, passwords, or certificates into the image.
- Build-time secrets go through `--mount=type=secret` and are exported through CLI: `docker buildx build --secret id=npm_token,env=NPM_TOKEN .` or `--secret id=npm_token,src=./secrets/npm_token`.
- `ARG` and `ENV` values are visible in image history via `docker history --no-trunc <image>`. Treat both as public.
- Runtime secrets come through environment variables, file mounts, or a secrets manager. Never the image.

```dockerfile
# Wrong: secret persists in image layer
COPY .env /app/.env

# Wrong: ARG values are visible in image history
ARG DATABASE_PASSWORD
ENV DATABASE_PASSWORD=$DATABASE_PASSWORD

# Correct: build-time secret, not persisted
RUN --mount=type=secret,id=npm_token \
    NPM_TOKEN=$(cat /run/secrets/npm_token) pnpm install
```

## HEALTHCHECK Pattern

Without a `HEALTHCHECK`, orchestrators treat the container as healthy the moment the process starts. Liveness probes are then orchestrator-specific and rarely portable.

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl --fail --silent --show-error http://127.0.0.1:8080/healthz || exit 1
```

| Flag | Guidance |
|------|----------|
| `--interval` | 30s for steady-state apps; 10s for dependency-heavy services |
| `--timeout` | 3s default; raise only if the endpoint is genuinely slow |
| `--start-period` | Generous on slow-booting apps; failures in this window do not count toward `--retries` |
| `--retries` | 3 to tolerate transient blips; 5 for cold-start-prone JVM or Python apps |

The check command must return non-zero on unhealthy. Distroless images have no shell; ship a small static health binary or expose a Unix socket the orchestrator probes directly. Compose can override the Dockerfile `HEALTHCHECK` via `healthcheck:`; production should set both.

## PID 1 and Signal Handling

A naked Node, Python, or shell entrypoint as PID 1 misses `SIGTERM`, leaks zombie children, and breaks graceful shutdown. Pick one:

| Option | When |
|--------|------|
| `docker run --init` | Ad-hoc runs and Compose; the daemon ships `tini` and runs it as PID 1 |
| Compose `init: true` per service | Long-lived services managed by Compose |
| `ENTRYPOINT ["tini", "--", "<app>"]` | Production images on any orchestrator |
| `dumb-init` in the entrypoint | Same role as `tini`; choose one project-wide |

```dockerfile
RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "dist/main.js"]
```

Without an init process, `kill -TERM <container>` may sit until `terminationGracePeriodSeconds` expires and then become `SIGKILL`. Open connections drop, in-flight writes corrupt. Cross-reference [`twelve-factor.md`](twelve-factor.md) Factor IX.

## Dockerfile Linting with Hadolint

[Hadolint](https://github.com/hadolint/hadolint) lints Dockerfiles against the Docker official best-practice rules plus shellcheck on every `RUN`.

```bash
hadolint Dockerfile
hadolint --config .hadolint.yaml Dockerfile
```

Rules to NEVER ignore:

| Rule | What it catches |
|------|-----------------|
| DL3000 | `WORKDIR` is not an absolute path |
| DL3008 | `apt-get install` without pinned versions |
| DL3018 | `apk add` without pinned versions |
| DL3025 | Shell-form `CMD`/`ENTRYPOINT` (breaks signal handling) |
| DL3059 | Multiple consecutive `RUN` statements (layer bloat) |
| DL4006 | Shell `RUN` without `set -o pipefail` |
| DL3007 | Missing tag (`FROM <image>`) |
| DL3027 | `apt` instead of `apt-get` (apt is interactive-only) |

Wire into CI:

```yaml
- name: Lint Dockerfile
  uses: hadolint/hadolint-action@v3.1.0
  with:
    dockerfile: Dockerfile
    failure-threshold: warning
```

`.hadolint.yaml` template:

```yaml
ignored: []
trustedRegistries:
  - docker.io
  - ghcr.io
  - cgr.dev
override:
  error: [DL3025, DL3027, DL4006]
  warning: [DL3008, DL3018]
```

Treat warnings as errors in CI. The cost of one Hadolint run is seconds; the cost of an unpinned base image causing a midnight outage is hours.

## Read-Only Root Filesystem

Mount the container's root filesystem as read-only. Applications write to explicitly defined volumes only.

```yaml
# Kubernetes pod spec
securityContext:
  readOnlyRootFilesystem: true
```

```yaml
# Compose service
read_only: true
tmpfs:
  - /tmp:rw,noexec,nosuid,size=64m
  - /run:rw,noexec,nosuid,size=16m
```

`noexec` blocks execution from the tmpfs. `nosuid` blocks suid escalation. Set both on every writable tmpfs unless the workload genuinely runs executables from `/tmp`.

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

```yaml
# Compose service
deploy:
  resources:
    limits:
      cpus: "1.0"
      memory: 512M
    reservations:
      memory: 256M
pids_limit: 512
ulimits:
  nofile:
    soft: 8192
    hard: 16384
  nproc: 4096
```

| Setting | Guidance |
|---------|----------|
| Memory request | Set to the application's steady-state usage |
| Memory limit | Set to 1.5x-2x the request. OOMKill above this |
| CPU request | Set to the minimum needed for acceptable performance |
| CPU limit | Set to handle burst load. Consider omitting to allow bursting |
| `pids_limit` | Cap process count; defends against fork bombs from a compromised container |
| `nofile` ulimit | Bound file-descriptor exhaustion |

- Always set memory limits. An unbounded container can trigger OOMKill on the node, affecting other workloads.
- Monitor actual usage and adjust. Overprovisioning wastes resources. Underprovisioning causes throttling and OOMKills.

## Compose Security Baseline

Most Docker security guidance covers Dockerfile and Kubernetes. Compose sits in the middle and is the most common production runtime for small fleets. The defaults are permissive. Override every one.

### Drop the version key

Compose v2 ignores the top-level `version:` field and prints a deprecation warning. Remove it from every file:

```yaml
# Wrong
version: "3.8"
services: ...

# Correct
name: myproject
services: ...
```

### Run as non-root

Either set `USER` in the Dockerfile or override per service:

```yaml
services:
  app:
    image: myapp:1.2.3@sha256:...
    user: "1001:1001"
```

### Read-only root + targeted tmpfs

```yaml
services:
  app:
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=64m
```

### Drop all capabilities, add only what is needed

```yaml
services:
  app:
    cap_drop: ["ALL"]
    cap_add: ["NET_BIND_SERVICE"]   # only if binding < 1024 without rootless
```

### security_opt no-new-privileges

Required on every service. Prevents `setuid` binaries from escalating, even if one slips into the image.

```yaml
services:
  app:
    security_opt:
      - no-new-privileges:true
```

### Ban host-namespace and privileged

Any of these is a CIS Docker 5.4 violation:

```yaml
# Forbidden
privileged: true
pid: host
ipc: host
network_mode: host
userns_mode: host
```

A privileged container has full host capabilities. Host-pid lets a container see, signal, and `ptrace` every host process. Host-network bypasses every network policy.

### Bind dev ports to loopback

`ports: "8080:8080"` listens on every interface, including Wi-Fi. Anyone on the same network reaches the dev service:

```yaml
# Wrong
ports:
  - "8080:8080"

# Correct for local dev
ports:
  - "127.0.0.1:8080:8080"
```

For internal-only services like a database serving the app container only, use `expose:` not `ports:`:

```yaml
services:
  db:
    expose:
      - "5432"
```

### Segment networks per tier

Define explicit networks. Mark backend networks `internal: true` so they have no route to the host or the internet:

```yaml
networks:
  frontend:
  backend:
    internal: true

services:
  web:
    networks: [frontend, backend]
  db:
    networks: [backend]
```

### Compose secrets

Never put credentials in `environment:`. Use top-level `secrets:` mounted at `/run/secrets/<name>`:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

Production-side options for `secrets:`:

| Source | Use |
|--------|-----|
| `file:` | Local development; the file must be `chmod 0400` and outside the build context |
| `environment:` | CI pipelines reading from a vault; the env var holds the secret material |
| `external: true` | Swarm mode or a sidecar that injects the secret before Compose runs |

Apps consume secrets via the `*_FILE` convention, e.g. `DB_PASSWORD_FILE=/run/secrets/db_password`. Plain Compose does not encrypt secrets at rest; encryption is a Swarm-mode feature. For production at scale, integrate with HashiCorp Vault, Infisical, or a cloud secrets manager.

### Healthchecks plus ordered startup

`depends_on` alone only sequences container starts. To wait until a dependency is actually ready, combine with `healthcheck:`:

```yaml
services:
  db:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 10s

  app:
    depends_on:
      db:
        condition: service_healthy
```

Valid `depends_on` conditions: `service_started`, `service_healthy`, `service_completed_successfully`.

### init true per service

```yaml
services:
  app:
    init: true
```

Compose injects `tini` as PID 1. Signal forwarding and zombie reaping become automatic.

### Restart policy

```yaml
services:
  app:
    restart: on-failure:5
```

Use `on-failure:<n>` over `always`. Always-restart loops on crashloops without backoff and hide the underlying bug. `unless-stopped` is acceptable for explicitly stateful services.

### Sysctls and ulimits

Namespace-aware sysctls only. Compose blocks non-namespaced sysctls by default; do not lift that:

```yaml
services:
  app:
    sysctls:
      net.ipv4.tcp_syncookies: 1
    ulimits:
      nofile:
        soft: 8192
        hard: 16384
```

### Profiles for environment-specific services

Gate dev-only services behind a profile. Production deployments omit the profile and the service does not start:

```yaml
services:
  mailcatcher:
    image: dockage/mailcatcher
    profiles: ["dev"]
```

Activate with `docker compose --profile dev up`. Default `docker compose up` starts only services without profiles.

### Compose develop.watch for local iteration

Replace volume-mount-and-restart with `develop.watch` on Compose v2.22+. Three actions:

| Action | When |
|--------|------|
| `sync` | Source-file change; copy into the container without restart |
| `rebuild` | Manifest or lockfile change; rebuild the image |
| `sync+restart` | Config-file change; sync and restart the main process |

```yaml
services:
  web:
    build: .
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: ./package.json
```

Watch mode is local dev only. Production never runs `docker compose watch`.

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
| Docker Scout | Policy-driven, integrates with Docker Hub and BuildKit attestations |

```bash
# Scan and fail on critical or high vulnerabilities
trivy image --severity CRITICAL,HIGH --exit-code 1 myapp:latest

# Docker Scout quickview with policy evaluation
docker scout quickview myapp:1.2.3
docker scout cves myapp:1.2.3 --only-severity critical,high --exit-code
```

- Scan in CI before pushing to the registry. Never push unscanned images.
- Scan the registry periodically. New CVEs are published after the image was built.
- Set policy: critical vulnerabilities block deployment. High vulnerabilities require a fix within 7 days.

## BuildKit Attestations

BuildKit attaches signed attestations to images at build time. Two types matter: SBOM and provenance.

```bash
# Produce both SBOM (SPDX-JSON via Syft) and full SLSA provenance
docker buildx build \
  --sbom=true \
  --provenance=mode=max \
  --tag myregistry/app:1.2.3 \
  --push .
```

| Flag | Effect |
|------|--------|
| `--sbom=true` | Generates an SPDX-JSON SBOM of the image and attaches it as an in-toto attestation |
| `--provenance=mode=min` | Default; minimal SLSA provenance with build invocation only |
| `--provenance=mode=max` | Full SLSA provenance with source URI, build parameters, environment |
| `--provenance=false` | Opt out; required for some legacy registries |
| `--attest=type=sbom,generator=...` | Override the SBOM generator; default is Syft |

Inspect an attestation:

```bash
docker buildx imagetools inspect myregistry/app:1.2.3 --format '{{ json .SBOM }}'
docker buildx imagetools inspect myregistry/app:1.2.3 --format '{{ json .Provenance }}'
```

Docker Scout's default Supply Chain Attestations policy fails when an image is missing an SBOM or provenance attestation. Wire `docker scout policy evaluate` into the deploy gate.

## Cosign and Image Signing

Sign container images to verify integrity and origin. Unsigned images in production are a supply chain risk.

```bash
# Keyless sign with Sigstore Fulcio; CI uses workload identity
cosign sign myregistry/app:1.2.3

# Key-based sign
cosign sign --key cosign.key myregistry/app:1.2.3

# Verify before deploying
cosign verify \
  --certificate-identity-regexp '^https://github\.com/myorg/.+$' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  myregistry/app:1.2.3
```

- Prefer keyless signing with Sigstore Fulcio and Rekor. No key material to store, rotate, or leak.
- Store key-based signing material in a secrets manager. Never in the repository.
- Enforce signature verification in the runtime or admission controller via Kyverno, Sigstore Policy Controller, or AWS Signer.
- Attestations are signed statements about the image. Signing only the image without attestations leaves SBOM and provenance unverifiable.

## Rootless Docker

Rootless mode runs both the daemon and the containers as an unprivileged user inside a user namespace. A compromised daemon yields the unprivileged user's privileges, not host root.

Setup prerequisites on Linux:

```bash
# Debian/Ubuntu
sudo apt-get install -y uidmap dbus-user-session
dockerd-rootless-setuptool.sh install
systemctl --user start docker
```

Trade-offs to know:

| Topic | Behavior |
|-------|----------|
| Ports below 1024 | Blocked. Use a reverse proxy or `sysctl net.ipv4.ip_unprivileged_port_start=80` |
| Networking | `slirp4netns` user-space networking; modest throughput hit |
| Overlay filesystem | Kernels older than 5.13 fall back to `fuse-overlayfs`; slower |
| Privileged containers | Not supported |
| Host mounts | Restricted to paths the unprivileged user can read |
| User-namespace CVEs | Still applicable; 2025 saw several namespace-bypass CVEs in Ubuntu's restrictions |

Rootless is the right default for new deployments where the trade-offs fit. It satisfies PCI DSS and HIPAA segmentation requirements. It is not a substitute for capability dropping, read-only roots, or no-new-privileges.

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
- For higher-assurance workloads, switch to `seccompProfile: Localhost` with a custom profile that allows only the syscalls the app makes.

## OWASP Docker Top 10 Mapping

| Control | Title | Where addressed in this file |
|---------|-------|------------------------------|
| D01 | Secure User Mapping | Non-Root Users; Rootless Docker; Compose Baseline Run-as-non-root |
| D02 | Patch Management Strategy | Pin Base Images by Digest; 2025 Docker Desktop Advisories; Image Scanning in CI |
| D03 | Network Segmentation and Firewalling | Compose Baseline Segment-networks; Compose Baseline Bind-dev-ports-to-loopback; Network Policies |
| D04 | Secure Defaults and Hardening | Minimal Base Images; Multi-Stage Builds; dockerignore Discipline; Security Context Defaults |
| D05 | Maintain Security Contexts | Security Context Defaults; Compose Baseline security_opt; Read-Only Root Filesystem |
| D06 | Protect Secrets | No Secrets in Image Layers; Compose Baseline Compose-secrets; [`standards/secrets-management.md`](secrets-management.md) |
| D07 | Resource Protection | Resource Limits |
| D08 | Container Image Integrity and Origin | Pin Base Images by Digest; BuildKit Attestations; Cosign and Image Signing |
| D09 | Follow Immutable Paradigm | Read-Only Root Filesystem; Compose Baseline Read-only-root |
| D10 | Logging | [`standards/observability.md`](observability.md) |

## 2025 Docker Desktop Advisories

| CVE | Component | Fixed in |
|-----|-----------|----------|
| CVE-2025-5843 | Docker Model Runner MLX inference backend, container-to-host RCE | Docker Desktop 4.71.0 |
| CVE-2025-5817 | Docker Model Runner vLLM-Metal backend, container-to-host RCE | Docker Desktop 4.68.0 |
| CVE-2025-33990 | Docker Model Runner OCI Registry Client SSRF | Docker Desktop 4.67.0 |
| CVE-2025-28400 | Docker Model Runner runtime flag injection | Docker Desktop 4.62.0 |
| CVE-2025-2664 | gRPC-FUSE kernel module out-of-bounds read | Docker Desktop 4.62.0 |
| CVE-2024-13743 | PAT leak in diagnostic bundles | Docker Desktop 4.54.0 |

Authoritative source: <https://docs.docker.com/security/security-announcements/>. Subscribe to updates; treat any new advisory in Docker Engine, BuildKit, runc, or Moby as in-scope for the current sprint.

## Related Standards

- [`standards/infrastructure.md`](infrastructure.md): Infrastructure as code, Kubernetes orchestration, CI/CD pipelines, cloud architecture
- [`standards/secrets-management.md`](secrets-management.md): Vault, External Secrets Operator, rotation
- [`standards/multi-account-cli.md`](multi-account-cli.md): Docker context isolation across machines and projects
- [`standards/twelve-factor.md`](twelve-factor.md): Factor IX disposability, PID 1, graceful shutdown
- [`standards/observability.md`](observability.md): Logging and runtime detection

# Infrastructure

## Infrastructure as Code

All infrastructure must be defined in code, versioned, and reproducible. Manual provisioning creates drift, makes recovery slow, and prevents environment parity.

### Principles

- **Declarative over imperative**: describe the desired state, let the tool converge. Terraform, Pulumi, CloudFormation, not bash scripts that `aws ec2 run-instances`.
- **Idempotent provisioning**: running the same code twice produces the same infrastructure. No orphaned resources, no duplicates.
- **Immutable infrastructure over configuration management**: bake dependencies into images (AMI, Docker), replace instances instead of patching them in place. Mutable servers drift over time and become unreproducible.

### State Management

| Concern | Approach |
|---------|----------|
| State storage | Remote backend (S3+DynamoDB, GCS, Terraform Cloud). Never local state for shared infrastructure |
| State locking | Enable locking to prevent concurrent modifications. DynamoDB for S3, native for Terraform Cloud |
| State isolation | Separate state per environment, per service, or per team. One blast radius per state file |
| Secrets in state | Terraform state contains plaintext secrets. Encrypt the backend, restrict access, consider `sensitive` flags |
| State recovery | State backup automated. Know the procedure for `terraform import` when state and reality diverge |

### Environment Parity

- Dev, staging, and production defined from the same templates with environment-specific variables.
- Use modules or components to share infrastructure definitions. Copy-pasted Terraform files between environments drift instantly.
- Test infrastructure changes in a lower environment before production. `terraform plan` is not a test.

### Drift Detection

- Run `terraform plan` on a schedule (CI cron job). If the plan shows changes, something was modified manually.
- Alert on drift. Manual changes to production infrastructure are an incident until proven otherwise.
- Fix drift by importing or re-applying, not by updating the code to match the manual change (unless the manual change was correct).

### Module Design

- Keep modules small and focused: one module per logical resource group (network, database, compute).
- Pin module versions. A module update should be an intentional change, not a surprise.
- Modules must accept all configurable values as variables. No hardcoded region, account ID, or environment name inside a module.
- Output everything downstream consumers need: ARNs, endpoints, security group IDs. Avoid forcing consumers to construct these from naming conventions.

## Networking and Service Discovery

Network design determines latency, security boundaries, and failure domains. Misconfigured networking is one of the hardest problems to debug in production.

### Service Discovery

| Pattern | How | When to use |
|---------|-----|-------------|
| DNS-based | Service registers with DNS (Route53, Cloud DNS, Consul). Clients resolve by name | Default for most services. Simple, works across platforms |
| Client-side | Client queries a registry (Consul, Eureka), gets a list of healthy instances, load-balances locally | When you need fine-grained load balancing or circuit breaking per client |
| Server-side | Load balancer (ALB, NLB, Cloud Load Balancing) routes traffic. Clients hit one endpoint | Default for external-facing services. Simpler client code |
| Service mesh | Sidecar proxy (Envoy/Istio, Linkerd) handles discovery, routing, mTLS, observability | When you need traffic management, observability, and security between services at scale |

### Load Balancing

Choose the algorithm based on the workload:

| Algorithm | Behavior | When to use |
|-----------|----------|-------------|
| Round-robin | Distribute evenly across backends | Stateless services with uniform request cost |
| Least connections | Route to the backend with fewest active connections | When request duration varies significantly |
| Consistent hashing | Route by a key (user ID, session ID) to the same backend | Stateful services, caching layers, sticky sessions |
| Weighted | Distribute by assigned weights | Canary deployments, gradual traffic shifting |

### DNS

- TTL must be configured for your failover requirements. A 300s TTL means up to 5 minutes of stale routing during failover.
- For services behind a load balancer, the DNS record points to the LB, not individual instances. The LB handles health checks.
- Use alias/CNAME records for cloud resources. Never hardcode IP addresses in DNS for dynamic infrastructure.

### Network Security

- **VPC design**: separate subnets for public, private, and data tiers. Database instances in private subnets with no public IP.
- **Security groups / firewall rules**: follow least privilege. Open only the ports needed, from only the sources needed. Default deny all inbound.
- **mTLS between services**: encrypt service-to-service traffic. The network is not a trust boundary, even inside a VPC.
- **Network policies**: in Kubernetes, default deny all ingress/egress. Explicitly allow only the traffic patterns your services need.
- **Egress control**: know what your services talk to externally. Unexpected egress is either a feature gap or a security incident.

### CDN and Edge

- Static assets and cacheable API responses behind a CDN. Reduces origin load and improves latency for global users.
- Cache invalidation strategy defined: TTL-based, versioned URLs, or explicit purge.
- Origin shield enabled when multiple CDN edge locations would hammer the origin.

## Container Orchestration

Kubernetes and container orchestration add operational complexity in exchange for deployment flexibility and resource efficiency. Use them deliberately.

### Resource Management

- **Requests**: minimum resources guaranteed to the container. Set based on actual usage under normal load. Under-requesting causes contention.
- **Limits**: maximum resources the container can use. Set based on peak usage plus headroom. Over-limiting causes OOM kills and CPU throttling.
- **Right-sizing**: measure actual usage with metrics (Prometheus, CloudWatch Container Insights), not guesswork. Review quarterly.
- **Resource quotas**: set per namespace to prevent one team or service from consuming the entire cluster.
- **Limit ranges**: set defaults and maximums per namespace so pods without explicit requests/limits get sane defaults.

### Scaling

| Type | Trigger | When to use |
|------|---------|-------------|
| Horizontal Pod Autoscaler (HPA) | CPU, memory, or custom metrics | Stateless services under variable load |
| Vertical Pod Autoscaler (VPA) | Historical resource usage | Single-instance workloads, databases, batch jobs |
| Cluster autoscaler | Pending pods that cannot be scheduled | When node capacity is the bottleneck, not pod count |
| KEDA (event-driven) | Queue depth, HTTP request rate, cron | When scaling should react to external signals, not just pod metrics |

- HPA and VPA cannot run on the same metric simultaneously. Choose one scaling axis per metric.
- Scale-down cooldown must be long enough to prevent thrashing. Scaling up is fast; scaling down too aggressively causes capacity gaps during the next spike.

### Availability

- **Pod disruption budgets**: define minimum available or maximum unavailable during voluntary disruptions (node drain, cluster upgrade). Without PDBs, a node drain can kill all replicas simultaneously.
- **Anti-affinity**: spread replicas across nodes and availability zones. Co-located replicas are a single point of failure.
- **Topology spread constraints**: for finer control over how pods distribute across zones, regions, or node groups.
- **Startup probes**: for slow-starting applications. Without a startup probe, the liveness probe may kill the container before it finishes initializing.
- **Graceful shutdown**: `preStop` hook with a sleep matching the deregistration time, `terminationGracePeriodSeconds` long enough to drain connections.

### Deployment Strategies

| Strategy | How | When to use |
|----------|-----|-------------|
| Rolling update | Replace pods incrementally. `maxUnavailable` and `maxSurge` control the pace | Default for most services. Zero downtime with backward-compatible changes |
| Blue/green | Two full deployments, traffic switched at the service or ingress level | When you need instant rollback and can afford 2x resources temporarily |
| Canary | Route a percentage of traffic to the new version, promote or rollback based on metrics | High-risk changes. Requires traffic splitting (Istio, Flagger, Argo Rollouts) |

### Sidecar Patterns

Sidecars handle cross-cutting concerns without modifying the application:

- **Service mesh proxy** (Envoy): mTLS, retries, circuit breaking, observability
- **Log collector** (Fluentd, Fluent Bit): ship logs to a central system without application changes
- **Secrets injector** (Vault Agent): inject secrets at runtime without baking them into the image

## Dockerfile Best Practices

Container images are deployment artifacts. A poorly built image is large, slow to pull, leaks secrets, and contains unnecessary attack surface.

### Build Strategy

- **Multi-stage builds**: use a builder stage for compilation and dependency installation, copy only the production artifact into the final stage. The final image should not contain compilers, build tools, or source code
- **Minimal base images**: prefer slim or distroless variants. Alpine (~5MB) over Debian (~130MB) over Ubuntu (~80MB). Evaluate on CVE count, image size, and native module compatibility. Alpine uses musl instead of glibc, which can break native modules in some ecosystems
- **Pin exact versions**: never use `latest`, `lts`, or floating tags. `node:22.5.1-alpine3.20`, not `node:lts`. Today's `latest` is tomorrow's breaking change

### Layer Optimization

- **Order by change frequency**: copy dependency manifests and install dependencies before copying source code. Source changes frequently; dependencies change rarely. This maximizes layer cache hits
- **.dockerignore**: exclude `.git`, `node_modules`, `.env`, test fixtures, documentation, and IDE configs. Reduces context size, speeds up builds, and prevents secrets from entering the image
- **Clean package manager cache**: remove cache directories (`npm cache clean --force`, `pip cache purge`, `apt-get clean`) in the same layer as the install to avoid bloating the image

### Security

- **Non-root user**: create a dedicated user and switch to it before the CMD. Never run application code as root. Set directory ownership explicitly when using WORKDIR with a non-root user
- **No build-time secrets in the final image**: use `--mount=type=secret` (BuildKit) or multi-stage builds to prevent credentials from persisting in image layers. `ARG` values are visible in image history
- **Image scanning**: scan images for CVEs in CI (Trivy, Grype, Snyk). Block deployment on critical/high findings. Scan on every build, not on a schedule
- **HEALTHCHECK directive**: define a HEALTHCHECK in the Dockerfile so the orchestrator knows when the container is ready. Without it, the container is marked healthy as soon as the process starts, even during initialization

### Runtime

- **Init process**: use `tini`, `dumb-init`, or `docker run --init` to handle PID 1 signal forwarding and zombie process reaping. See `standards/twelve-factor.md` Factor IX for details
- **Production-only dependencies**: exclude dev dependencies from the final image. Install with `--omit=dev`, `--only=production`, or equivalent
- **Single concern per container**: one process per container. Do not run application server, cron daemon, and log rotator in the same container

## CI/CD Pipeline Design

A good pipeline catches problems early, deploys safely, and provides fast feedback. A bad pipeline is slow, flaky, and gives false confidence.

### Pipeline Stages

Stages should run in order of feedback speed: fastest checks first, slowest last.

1. **Lint and static analysis**: seconds. Catches formatting, type errors, known anti-patterns.
2. **Unit tests**: seconds to minutes. Fast feedback on logic correctness.
3. **Build**: minutes. Produces the deployable artifact (Docker image, binary, package).
4. **Integration tests**: minutes. Verifies interactions with real dependencies (database, APIs).
5. **Security scan**: minutes. Dependency audit, container scan, SAST.
6. **Deploy to staging**: minutes. Apply infrastructure changes and deploy the artifact.
7. **E2E / smoke tests**: minutes. Verify critical paths in a production-like environment.
8. **Deploy to production**: minutes to hours depending on rollout strategy.

### Artifact Immutability

- Build the artifact once. Promote the same image/binary through all environments. Never rebuild for production.
- Tag artifacts with the git SHA. `latest` is not a deployment strategy.
- Store artifacts in a registry with retention policies. Clean up old images to control storage costs.
- Sign artifacts. Verify signatures before deployment. Prevents deploying tampered images.

### Environment Promotion

| Strategy | How | When to use |
|----------|-----|-------------|
| Push-based | CI pipeline deploys to each environment in sequence | Simpler setup. Good for smaller teams |
| GitOps | Changes merged to an environment branch trigger deployment (ArgoCD, Flux) | Audit trail, declarative, self-healing. Good for Kubernetes |
| Manual promotion | CI builds and tests. Human triggers promotion to production | When regulatory or compliance requirements demand explicit approval |

### Progressive Delivery

- **Canary**: deploy to a small percentage of traffic, monitor key metrics (error rate, latency, business metrics), auto-promote or auto-rollback based on thresholds.
- **Feature flags**: deploy code to all instances, gate behavior behind a flag. Enable gradually per user segment, geography, or percentage.
- **Dark launching**: deploy the new code path, run it in shadow mode alongside the old path, compare results. No user impact.

### Pipeline Security

- Secrets injected at runtime, never stored in the repository or build logs.
- Dependency scanning runs on every build, not just on a schedule.
- Pipeline permissions follow least privilege. The deploy step has deploy credentials, the test step does not.
- Audit trail: who triggered what, when, with what parameters.

### DORA Metrics

Track these to measure engineering effectiveness:

| Metric | What it measures | Elite target |
|--------|-----------------|-------------|
| Deployment frequency | How often you ship to production | On demand (multiple times per day) |
| Lead time for changes | Time from commit to production | Less than one hour |
| Change failure rate | Percentage of deployments causing incidents | Less than 5% |
| Mean time to recovery (MTTR) | Time to restore service after an incident | Less than one hour |

## Cloud Architecture

Cloud architecture decisions have long-lasting consequences. They affect cost, reliability, security, and operational complexity for years.

### Multi-Region

| Strategy | How | When to use | Cost |
|----------|-----|-------------|------|
| Single region | All resources in one region | Non-critical services, cost-sensitive | Lowest |
| Active-passive | Primary region serves traffic, secondary on standby for failover | When RTO of minutes to an hour is acceptable | Medium |
| Active-active | Both regions serve traffic simultaneously | When RTO must be near-zero, or users span geographies | Highest |

Active-active introduces data replication complexity. Every write must reach both regions, and you must choose between synchronous replication (higher latency) and asynchronous (data loss window during failover).

### Blast Radius Containment

- **Account isolation**: separate AWS accounts or GCP projects per environment and per workload class (production, staging, shared services). One compromised account does not affect others.
- **Cell-based architecture**: partition the system into independent cells (by geography, customer segment, or shard). A failure in one cell does not cascade to others.
- **Service quotas**: know the cloud provider limits for your resources (EC2 instances, Lambda concurrency, API Gateway requests). Monitor usage against limits. Hitting a quota in production is an outage.
- **AZ-independent**: design so losing one availability zone does not degrade service. Spread resources across at least 2 AZs, prefer 3.

### Auto-scaling

- **Predictive scaling**: use scheduled scaling or ML-based prediction for known traffic patterns (daily peaks, weekly cycles, marketing campaigns). Reactive scaling has a lag.
- **Reactive scaling**: HPA, target tracking policies. Set the target metric (CPU, request count, queue depth) and let the autoscaler adjust. Always set a minimum and maximum.
- **Scale-to-zero**: for event-driven or batch workloads (Lambda, Cloud Run, Knative). No cost when idle. Cold start latency is the trade-off.
- **Cooldown periods**: prevent thrashing by requiring a minimum time between scale-in events. Scale-out should be aggressive, scale-in conservative.

### Traffic Management

| Pattern | How | When to use |
|---------|-----|-------------|
| Weighted routing | Route a percentage of traffic to different targets (Route53 weighted, GCP Traffic Director) | Canary deployments, gradual migrations |
| Geolocation routing | Route by user geography | Latency optimization, data residency compliance |
| Failover routing | Health-check-based automatic failover to secondary region | Disaster recovery |
| Header-based routing | Route by request header (feature flag, tenant ID, version) | A/B testing, tenant isolation, API versioning |

### DDoS and Edge Protection

- **WAF (Web Application Firewall)**: rate limiting, IP reputation, SQL injection blocking, bot detection at the edge.
- **Shield / Armor**: cloud-native DDoS protection for volumetric attacks. Enable on all public-facing load balancers.
- **Rate limiting at the edge**: CDN or API gateway level. Don't let attack traffic reach your application servers.

### Data Residency

- Know where your data is stored and processed. Some regulations (GDPR, LGPD) restrict cross-border data transfer.
- Choose cloud regions based on both latency and compliance requirements.
- If multi-region, ensure replication respects residency constraints. Data from EU users must not replicate to US regions without a legal basis.

### Cost Allocation

- **Tag everything**: environment, team, service, cost center. Without tags, cost attribution is guesswork.
- **Reserved capacity**: for stable, predictable workloads. Savings Plans or Reserved Instances provide 30-60% savings.
- **Spot / preemptible instances**: for fault-tolerant workloads (batch processing, CI runners, stateless workers). 60-90% savings with interruption risk.
- **Right-sizing**: review instance types quarterly. Most services are over-provisioned after the initial launch.

## Zero-Downtime Deployment Strategies

| Strategy | Best for | Rollback speed | Cost |
|----------|----------|----------------|------|
| Blue-Green | Infrastructure updates | Instant (traffic switch) | High (2x environments) |
| Canary | Application code changes | Fast (redirect traffic) | Medium |
| Rolling | Container workloads | Moderate (batch reversion) | Low |

Rules:

- Blue-Green: maintain two identical environments, instant traffic switch, simple rollback
- Canary: start with 1-5% traffic, monitor error rates and latency, gradually increase. Automated rollback on regression
- Rolling: sequential batch updates across instances. Orchestrator manages the update order
- Progressive delivery: combine deployment strategies with feature flags to control who accesses features, not just when code deploys
- Database migrations must be backward-compatible with the previous application version

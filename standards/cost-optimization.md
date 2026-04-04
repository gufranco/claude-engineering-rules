# Cost Optimization

Checklist reference: `checklists/checklist.md` category 42 (Cost Awareness).

## Cost Allocation

Every cloud resource must be tagged. Without tags, cost attribution is guesswork, and guesswork leads to uncontrolled spending.

### Mandatory Tags

| Tag key | Purpose | Example values |
|---------|---------|---------------|
| `environment` | Separate prod from non-prod spend | `production`, `staging`, `development`, `preview` |
| `team` | Attribute cost to the owning team | `platform`, `payments`, `growth` |
| `service` | Attribute cost to the specific service | `order-api`, `notification-worker`, `cdn-origin` |
| `cost-center` | Financial reporting rollup | `eng-001`, `infra-002` |
| `managed-by` | Distinguish IaC-managed from manual resources | `terraform`, `pulumi`, `manual` |

### Tag Enforcement

- **In IaC**: use a provider-level `default_tags` block or equivalent. Every resource inherits the mandatory set without per-resource boilerplate.

```hcl
# Terraform AWS example
provider "aws" {
  default_tags {
    tags = {
      environment = var.environment
      team        = var.team
      service     = var.service
      cost-center = var.cost_center
      managed-by  = "terraform"
    }
  }
}
```

- **In CI**: add a tag validation step that fails the pipeline when a resource is missing any mandatory tag. Tools: `tflint` with the AWS/GCP ruleset, AWS Config rules, or a custom `terraform plan` output parser.
- **Drift detection**: run a weekly scheduled job that reports untagged resources. Any untagged resource in production is a finding that must be resolved within 5 business days.

## Compute Optimization

### Right-Sizing Methodology

Measure actual utilization before choosing instance types. Guesswork over-provisions by 40-60% on average.

| Metric | Under-utilized threshold | Action |
|--------|------------------------|--------|
| Average CPU over 14 days | < 20% | Downsize to the next smaller instance family or type |
| Peak CPU over 14 days | < 40% | Downsize. The peak confirms headroom is excessive |
| Average memory over 14 days | < 30% | Switch to a compute-optimized family or reduce instance size |
| Peak memory over 14 days | < 50% | Downsize. Memory headroom is safe to reduce |
| Average CPU over 14 days | > 80% | Upsize or add horizontal scaling |
| Peak CPU over 14 days | > 95% | Upsize immediately. Saturation causes latency degradation |

Review compute sizing quarterly. Traffic patterns shift, and an instance that was right-sized six months ago may be wasting 30% now.

### Commitment Strategy

| Workload profile | Strategy | Savings vs on-demand |
|-----------------|----------|---------------------|
| Steady-state, predictable 24/7 | Savings Plans (compute) or 1-year reserved instances | 30-40% |
| Stable but specific instance type | 1-year reserved instances (standard) | 35-45% |
| Long-term stable, low risk of change | 3-year reserved instances | 50-60% |
| Variable but with a known baseline | Savings Plans covering the baseline, on-demand for bursts | 20-30% blended |
| New service, usage unknown | On-demand for 30-60 days, then commit after observing the baseline | 0% initially, commit after data |

Rules:
- Never purchase commitments for a service that has been running less than 30 days.
- Savings Plans over Reserved Instances when the workload may change instance types or regions.
- Reserved Instances only when locked into a specific instance family in a specific region.
- Track commitment coverage monthly. Target: 70-80% of steady-state compute covered by commitments.

### Spot and Preemptible Instances

Use spot instances for workloads that tolerate interruption. 60-90% savings.

| Workload | Spot eligible | Requirements |
|----------|--------------|-------------|
| CI/CD runners | Yes | Retry on interruption, stateless build agents |
| Batch processing | Yes | Checkpointing, idempotent jobs |
| Stateless API workers behind a load balancer | Yes, mixed with on-demand | Minimum on-demand baseline, spot for burst capacity |
| Databases | No | Data durability requires stable instances |
| Single-instance services | No | Interruption causes downtime |
| Queue consumers | Yes | Messages re-delivered on interruption |

Rules:
- Diversify across at least 3 instance types and 2 availability zones to reduce interruption probability.
- Set a maximum spot price at the on-demand rate. Never bid above on-demand.
- Use capacity-optimized allocation strategy, not lowest-price. Lowest-price pools drain first.
- Implement a 2-minute interruption handler that drains connections and checkpoints state.

### Auto-Scaling

| Scaling policy | How it works | When to use |
|---------------|-------------|-------------|
| Target tracking | Maintain a target metric value (e.g., CPU at 60%) | Default for most services. Simple, self-adjusting |
| Step scaling | Add/remove capacity in defined steps at defined thresholds | When target tracking oscillates or you need different responses at different load levels |
| Scheduled scaling | Pre-scale at known times | Predictable traffic patterns: business hours, marketing campaigns, batch windows |
| Predictive scaling | ML-based forecasting from historical patterns | Daily/weekly cyclical patterns with enough history (14+ days) |

Rules:
- Set a minimum instance count that can survive a single AZ failure without degradation.
- Set a maximum instance count that limits runaway scaling costs. A missing maximum is an unbounded cost risk.
- Scale-out aggressively, scale-in conservatively. Scale-out cooldown: 60 seconds. Scale-in cooldown: 300 seconds minimum.
- Target tracking at 60-70% CPU for compute-bound workloads. For latency-sensitive services, track request latency or queue depth instead of CPU.

## Storage Optimization

### S3/GCS Lifecycle Policies

Every bucket must have a lifecycle policy. Unmanaged buckets accumulate data indefinitely.

| Data age | Storage class | Approximate savings vs standard |
|----------|--------------|-------------------------------|
| 0-30 days | Standard | Baseline |
| 30-90 days | Infrequent Access (S3 IA / GCS Nearline) | 40-45% |
| 90-365 days | Glacier Instant Retrieval / GCS Coldline | 60-70% |
| 1-7 years | Glacier Deep Archive / GCS Archive | 90-95% |
| > 7 years | Delete unless regulatory hold | 100% |

Rules:
- Define lifecycle rules in IaC, not through the console.
- Enable S3 Intelligent-Tiering for buckets with unpredictable access patterns. The monitoring fee (per-object) is cheaper than storing cold data in standard tier.
- Delete incomplete multipart uploads after 7 days. They accumulate invisibly and cost money.
- Enable bucket metrics to identify large, rarely accessed objects.

### Log Retention

| Log type | Retention period | Storage tier |
|----------|-----------------|-------------|
| Application logs | 30 days hot, 90 days warm | CloudWatch / Elasticsearch (hot), S3 IA (warm) |
| Access logs | 90 days hot, 1 year archive | Same pattern |
| Audit logs | 1 year hot, 7 years archive (or per regulatory requirement) | Hot store, then Glacier |
| Debug logs | 7 days | Hot only, auto-delete |
| CI/CD build logs | 30 days | Hot only, auto-delete |

Rules:
- Set retention policies at log group creation time in IaC. A log group created without a retention policy retains forever.
- Never store debug-level logs in production for more than 7 days. The volume is high and the value decays fast.
- Compress logs before archiving. Typical compression ratio for JSON logs: 10:1.

### Database Storage

- Enable storage autoscaling with a maximum limit. An unbounded autoscale is a cost risk.
- Review allocated storage vs used storage quarterly. Over-provisioned IOPS on EBS/Persistent Disk is a common waste.
- Use GP3 over GP2 for EBS volumes. GP3 allows independent IOPS and throughput configuration at a lower base cost.

### Unused Volume Cleanup

- Run a weekly scan for unattached EBS volumes and persistent disks. Detached volumes still incur charges.
- Delete orphaned snapshots older than 90 days that are not part of an AMI or backup policy.
- Automate cleanup with a scheduled Lambda/Cloud Function that tags unattached volumes and deletes them after a 14-day grace period.

## Network Cost Reduction

### VPC Endpoints vs NAT Gateway

NAT gateways charge per GB processed. For services that make heavy API calls to AWS services from private subnets, the NAT gateway data processing cost dominates.

| Traffic pattern | Solution | Cost impact |
|----------------|----------|-------------|
| S3 access from private subnets | Gateway VPC endpoint (free) | Eliminates NAT charges for S3 traffic |
| DynamoDB from private subnets | Gateway VPC endpoint (free) | Eliminates NAT charges for DynamoDB traffic |
| Other AWS services (SQS, SNS, KMS, ECR) | Interface VPC endpoints (~$7/month/AZ + per-GB) | Cheaper than NAT when monthly data > 50GB per service |
| Internet-bound traffic | NAT gateway (required) | No alternative for true internet egress |

Rules:
- Always create gateway endpoints for S3 and DynamoDB in every VPC with private subnets. They are free.
- Create interface endpoints for any AWS service where monthly data transfer exceeds 50GB.
- Deploy NAT gateways in a single AZ for non-production environments. Production requires one per AZ for redundancy.

### CDN for Static Assets

- Serve all static assets (JS, CSS, images, fonts) through a CDN. Reduces origin bandwidth and improves latency.
- Set long cache TTLs (1 year) with content-hashed filenames for immutable assets. Eliminates unnecessary origin fetches.
- Use origin shield to reduce multi-edge origin hits to a single request.

### Data Transfer Optimization

| Transfer type | Cost | Mitigation |
|--------------|------|-----------|
| Same AZ | Free (most providers) | Co-locate services that communicate frequently |
| Cross-AZ | ~$0.01/GB each direction (AWS) | Accept this cost for redundancy. Do not sacrifice availability to save on cross-AZ transfer |
| Cross-region | ~$0.02/GB (AWS) | Replicate only what is necessary. Use regional read replicas instead of cross-region API calls |
| Internet egress | ~$0.09/GB (AWS, first 10TB) | CDN, compression, pagination, efficient serialization |

Rules:
- Co-locate services that exchange high volumes of data in the same AZ when availability requirements allow.
- Compress API responses. Enable gzip/brotli at the load balancer or application level. Typical compression ratio for JSON: 5:1-10:1.
- Use pagination and field selection to reduce response payload sizes. Do not transfer 100 fields when the client needs 5.

## Database Cost Optimization

### Aurora Serverless ACU Tuning

| Configuration | Impact |
|--------------|--------|
| Minimum ACU too high | Paying for idle capacity during low-traffic periods |
| Minimum ACU too low (0.5) | Cold start latency of 20-30 seconds on first connection after idle |
| Maximum ACU too low | Queries throttled during peak load, causing application errors |
| Maximum ACU too high | Unbounded cost during traffic spikes or runaway queries |

Rules:
- Set minimum ACU to the value that sustains your lowest traffic period without cold starts. For services with continuous traffic, minimum ACU of 2-4 is typical.
- Set maximum ACU based on the peak load observed over 30 days plus 50% headroom.
- Enable auto-pause only for development environments. Production databases must not have cold start latency.
- Monitor ACU utilization weekly. If the minimum ACU is never reached, lower it. If the maximum is frequently hit, raise it or investigate the queries.

### RDS Instance Right-Sizing

Follow the same CPU/memory thresholds from the Compute Optimization section. Additionally:

- Use `Performance Insights` to identify whether the bottleneck is CPU, I/O, or lock contention before upsizing.
- Graviton (ARM) instances provide 20-30% better price-performance than equivalent x86 instances.
- Multi-AZ is mandatory for production. The cost is 2x the single-AZ price, but the alternative is downtime during AZ failure.
- Use reserved instances for production databases. Database workloads are the most predictable compute, making commitments low-risk.

### Read Replicas

| Pattern | When to use | Cost impact |
|---------|-------------|-------------|
| Read replica for read-heavy queries | Read:write ratio > 5:1 | Replica cost + reduced primary load, net savings if it allows a smaller primary |
| Read replica for reporting/analytics | Long-running queries that would degrade OLTP performance | Isolates analytical load from production traffic |
| Cross-region read replica | Users in multiple regions need low-latency reads | Replica cost + cross-region replication, justified by latency improvement |

Rules:
- Route read-only queries to replicas explicitly in the application. A replica that receives no traffic is pure waste.
- Monitor replica lag. Queries that require strong consistency must go to the primary.
- Use connection-level routing (ProxySQL, PgBouncer, RDS Proxy) to distribute reads automatically when the application supports it.

### Connection Pooling

- Use a connection pooler (RDS Proxy, PgBouncer, ProxySQL) for all serverless and high-concurrency workloads.
- Without pooling, each Lambda invocation or container opens a new connection. 1000 concurrent functions create 1000 connections, exceeding the database connection limit and forcing an unnecessarily large instance.
- With pooling, the same 1000 functions share a pool of 50-100 connections. This allows a smaller database instance, saving 30-50% on compute.

## Monitoring and Alerting

### Budget Alerts

Configure multi-threshold budget alerts for every account and every tagged service.

| Threshold | Action |
|-----------|--------|
| 50% of monthly budget | Informational notification to the team channel |
| 80% of monthly budget | Warning notification to the team channel and engineering lead |
| 100% of monthly budget | Alert to engineering lead and finance |
| 120% of monthly budget (forecast) | Alert to engineering director and finance, requires same-day investigation |

Rules:
- Create budgets in IaC, not through the console. Console-created budgets are invisible to the team.
- Set budgets at two levels: account-level and per-service (using cost allocation tags).
- Use forecasted alerts in addition to actual spend alerts. A 120% forecast alert gives time to act before the month ends.

### Cost Anomaly Detection

- Enable AWS Cost Anomaly Detection or equivalent for every account. It identifies unexpected spend spikes using ML.
- Set anomaly alert thresholds at the lower of: $100/day increase or 20% above the trailing 7-day average.
- Route anomaly alerts to the same channel as budget alerts. Every anomaly must be investigated within 24 hours.

### Daily Cost Reports

- Generate a daily cost report broken down by service, environment, and team tags.
- Automate delivery to a shared channel (Slack, email).
- Include day-over-day and week-over-week comparisons. A 15% day-over-day increase requires investigation.

### Per-Service Cost Attribution

- Build a dashboard showing monthly cost per service using cost allocation tags.
- Include trend lines: is each service's cost growing, stable, or declining?
- Review per-service cost in monthly engineering meetings. The owning team must explain any month-over-month increase above 10%.

## Development Environment Cost

### Non-Production Environment Scheduling

Non-production environments that run 24/7 waste 65-75% of their compute budget.

| Environment | Schedule | Savings |
|-------------|----------|---------|
| Development | Business hours only: Mon-Fri 08:00-20:00 local time | ~65% |
| Staging | Business hours only, with on-demand start for testing | ~65% |
| Preview/ephemeral | Destroy after PR merge or 24 hours of inactivity | ~90% |
| Load testing | Provision on demand, destroy after test completion | ~95% |
| Production | 24/7, no scheduling | 0% |

Rules:
- Implement scheduling using AWS Instance Scheduler, GCP VM Schedule, or equivalent IaC-managed automation.
- Provide a self-service mechanism (Slack command, CI workflow) to start a stopped environment when a developer needs it outside business hours.
- RDS instances in non-production environments must use the `stop` and `start` API, not just stopping the EC2 instances that connect to them. A stopped application with a running database still costs money.

### Shared vs Dedicated Dev Environments

- Use shared development environments for services under active development by multiple engineers. One environment per team, not per developer.
- Dedicated environments only when isolation is genuinely required: incompatible schema migrations, experimental infrastructure changes.
- Shared environments must have namespace or schema isolation per developer to prevent conflicts.

### Ephemeral Preview Environments

- Provision preview environments per PR using IaC (Terraform workspaces, Pulumi stacks, or platform-native preview features).
- Auto-destroy on PR merge or close.
- Set a hard TTL of 72 hours for open PRs. If the PR is still open, recreate on the next push.
- Use the smallest viable instance types. Preview environments serve 1-2 developers, not production traffic.

### Local Development Over Cloud

- Default to local development (Docker Compose, local databases, local queues) for daily coding.
- Cloud development environments only when local is impractical: GPU workloads, large datasets, platform-specific testing.
- Document the local development setup in the project README. If it takes more than 3 commands to start, fix the setup.

## FinOps Practices

### Monthly Cost Review

Hold a monthly cost review meeting with engineering leads and finance.

Agenda:
1. Total spend vs budget (actual and forecast).
2. Top 5 cost drivers and month-over-month change.
3. Commitment utilization and coverage.
4. Anomalies and investigations from the past month.
5. Action items from the previous review: were they completed?

Every action item must have an owner and a due date. "We'll look into it" is not an action item.

### Unused Resource Cleanup

| Resource type | Detection method | Cleanup cadence |
|--------------|-----------------|----------------|
| Unattached EBS volumes | AWS Config rule or custom script | Weekly automated scan, 14-day grace, then delete |
| Idle load balancers (0 healthy targets) | CloudWatch `HealthyHostCount` = 0 for 7 days | Weekly scan, notify owner, delete after 14 days |
| Unused Elastic IPs | AWS Config rule | Weekly scan, immediate release if unattached |
| Old AMIs and snapshots | Age > 90 days without recent launch | Monthly scan, owner review, delete after approval |
| Idle RDS instances (0 connections for 7 days) | CloudWatch `DatabaseConnections` = 0 | Weekly scan, notify owner, stop after 7 days, delete after 30 |
| Unused NAT gateways | CloudWatch `BytesOutToDestination` = 0 for 7 days | Weekly scan, delete after owner confirmation |
| Orphaned Lambda functions (0 invocations for 30 days) | CloudWatch `Invocations` = 0 | Monthly scan, notify owner, delete after 14 days |

Rules:
- Automate detection. Manual audits happen once and then stop.
- Every detected resource gets a notification to the owning team before deletion.
- Grace periods are mandatory. Never auto-delete without warning.
- Tag resources with a `delete-after` date when they are known to be temporary.

### Commitment Coverage Tracking

| Metric | Target | Review cadence |
|--------|--------|---------------|
| Savings Plan coverage (% of eligible on-demand spend covered) | 70-80% | Monthly |
| Reserved Instance utilization (% of reserved capacity actually used) | > 95% | Monthly |
| Savings Plan utilization (% of committed spend actually used) | > 95% | Monthly |
| Commitment expiration in next 30 days | 0 unplanned expirations | Weekly |

Rules:
- Review expiring commitments 60 days before expiration. Decide: renew, resize, or let expire.
- Never auto-renew commitments. Traffic patterns change. Re-evaluate the workload before renewing.
- When utilization drops below 90%, investigate immediately. A commitment at 80% utilization means 20% is wasted.
- Track commitment coverage as a dashboard metric visible to the entire engineering org.

## Related Standards

- `standards/infrastructure.md`: Infrastructure
- `standards/sre-practices.md`: SRE Practices

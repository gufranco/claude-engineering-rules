# Data Pipelines

## Pipeline Types

| Type | Execution | Latency | Use case |
|------|-----------|---------|----------|
| Batch | Scheduled intervals (hourly, daily) | Minutes to hours | Reports, aggregations, ML training, data warehouse loads |
| Micro-batch | Short intervals (seconds to minutes) | Seconds | Near-real-time dashboards, incremental processing |
| Streaming | Continuous, event-driven | Milliseconds | Real-time analytics, fraud detection, live feeds |

**Default rule**: start with batch. Move to streaming only when latency requirements demand it. Streaming pipelines are harder to debug, test, and operate.

## Idempotency

Every pipeline stage must be safe to re-run. Failures, retries, and backfills all re-execute stages.

- Use upsert or merge operations, not blind inserts
- Partition output by processing window. Re-running overwrites the partition, not the entire dataset
- Track processed offsets or watermarks. Resume from the last committed position after failure
- Design for "at-least-once" processing and deduplicate downstream

## Backfill Strategy

When historical data needs reprocessing:

- Support a date range parameter on every pipeline. `--start 2026-01-01 --end 2026-01-31` reprocesses January
- Backfills run on the same code path as normal runs. No special backfill scripts
- Limit parallelism during backfill to avoid overwhelming source systems
- Monitor source system load during backfill. If latency increases, throttle

## Data Quality

Validate data at every stage boundary, not just at the end.

| Check | What to validate | Action on failure |
|-------|-----------------|-------------------|
| Schema validation | Fields exist, types match, required fields non-null | Reject record, send to DLQ |
| Freshness | Data arrived within expected window | Alert if stale |
| Volume | Row count within expected range (no sudden drops or spikes) | Alert, pause pipeline if threshold exceeded |
| Uniqueness | No unexpected duplicates on key columns | Deduplicate or alert |
| Referential integrity | Foreign keys resolve to existing records | Reject or quarantine |

## Error Handling

- **Record-level failures**: isolate and quarantine bad records. Process the rest of the batch. Never let one bad record fail the entire pipeline
- **Stage-level failures**: retry the stage with backoff. After max retries, alert and pause
- **Source unavailability**: retry with exponential backoff. If the source is down for extended periods, pause and resume when available
- **Poison messages**: records that fail repeatedly after retries go to a dead letter store with full context (original payload, error, timestamp, attempt count)

## Monitoring

| Metric | What it tells you |
|--------|-------------------|
| Records processed per interval | Throughput and whether the pipeline keeps up |
| Processing latency (p50, p95, p99) | How long each record takes |
| Error rate | Percentage of failed records |
| Lag (streaming) | How far behind real-time the pipeline is |
| Last successful run (batch) | Whether the pipeline ran on schedule |
| DLQ depth | How many records need manual attention |

Alert on: lag exceeding SLA, error rate above threshold, missed scheduled runs, DLQ depth growing.

## Testing

- **Unit test transformations**: pure functions that transform records, tested with sample data
- **Integration test stages**: each stage reads from a test source and writes to a test sink. Verify output matches expected
- **End-to-end test the full pipeline**: run with a small representative dataset. Verify final output
- **Test idempotency explicitly**: run the same input twice, verify the output is identical
- **Test backfill**: run with a historical date range, verify it produces correct results
- **Test failure handling**: inject bad records, verify they are quarantined and good records proceed

## ETL vs ELT

| Approach | Transform location | When to use |
|----------|-------------------|-------------|
| ETL | Transform before loading into the target | When the target has limited compute (OLTP databases, APIs) |
| ELT | Load raw data, transform in the target | When the target is a data warehouse with strong compute (BigQuery, Snowflake, Redshift) |

**Default rule**: prefer ELT when loading into a data warehouse. Raw data in the warehouse enables ad-hoc analysis without re-running the pipeline.

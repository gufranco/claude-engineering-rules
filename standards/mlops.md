# MLOps

## Model Lifecycle

| Phase | Artifacts | Validation |
|-------|-----------|------------|
| Training | Model weights, hyperparameters, training metrics | Loss convergence, no overfitting (train vs validation gap) |
| Evaluation | Evaluation metrics on held-out test set | Meets threshold on primary metric before promotion |
| Registration | Versioned model in a registry (MLflow, SageMaker, Vertex AI) | Metadata includes training data version, code commit, metrics |
| Deployment | Model behind a serving endpoint | Canary rollout, A/B test, or shadow mode before full traffic |
| Monitoring | Inference metrics, drift alerts | Automated retraining trigger when drift exceeds threshold |

## Experiment Tracking

Every training run must be reproducible. Track:

- Code version (git commit hash)
- Data version (dataset hash or snapshot ID)
- Hyperparameters (all of them, not just the ones you changed)
- Environment (Python version, CUDA version, library versions)
- Metrics (training loss, validation metrics at every epoch)
- Artifacts (model weights, plots, confusion matrices)

Use MLflow, Weights & Biases, or Neptune. Never rely on local files or notebook output for experiment records.

## Feature Stores

Centralize feature computation to avoid training/serving skew.

- Features computed for training must use the same code path as features computed at inference time
- Store features with timestamps. Point-in-time lookups prevent data leakage (using future data during training)
- Separate offline (batch) and online (low-latency) stores. Sync between them with a materialization job
- Version features. A model trained on feature v2 must be served with feature v2

## Model Serving

| Pattern | Latency | When to use |
|---------|---------|-------------|
| REST/gRPC endpoint | Milliseconds | Real-time predictions (recommendations, fraud scoring) |
| Batch inference | Minutes to hours | Periodic scoring of large datasets (email campaigns, risk assessment) |
| Embedded model | Microseconds | Edge devices, mobile apps, latency-critical paths |
| Streaming inference | Milliseconds, continuous | Event-driven predictions on streaming data |

- Set explicit timeout and fallback behavior. If the model endpoint is slow, return a default prediction, not an error
- Version endpoints: `/v1/predict`, `/v2/predict`. Run old and new versions simultaneously during transition
- Rate limit inference endpoints. A runaway client can exhaust GPU capacity

## Data and Model Drift

Models degrade over time as the real-world distribution shifts away from training data.

| Drift type | What changed | Detection |
|------------|-------------|-----------|
| Data drift | Input feature distributions shifted | Statistical tests (KS test, PSI) on feature distributions |
| Concept drift | Relationship between features and target changed | Monitor prediction accuracy against ground truth |
| Label drift | Target variable distribution shifted | Compare target distribution over time windows |

- Monitor drift continuously, not on a schedule. By the time a weekly check catches drift, a week of bad predictions already happened
- Set automated retraining triggers. When drift score exceeds the threshold, kick off a retraining pipeline
- Always validate the retrained model against the current production model before promoting

## Testing

- **Unit test feature engineering**: pure transformations on sample data
- **Integration test the training pipeline**: run on a small dataset, verify the model saves and loads correctly
- **Test model quality gates**: verify that evaluation metrics meet thresholds before promotion
- **Test serving infrastructure**: load test the endpoint, verify latency and throughput under expected load
- **Test rollback**: verify that reverting to the previous model version works and serves correct predictions
- **Test training/serving parity**: compute features through both paths on the same input, verify they match

## Related Standards

- `standards/observability.md`: Observability
- `standards/data-pipelines.md`: Data Pipelines

# Phase 4A: Offline Synthetic Behavioural Anomaly Detection

Phase 4A adds reproducible offline behavioural scoring to AegisTwin. Every dataset, artifact, score, assessment, and evaluation is synthetic. An anomaly means that an event differs from the learned synthetic normal baseline; it does not mean an attack, compromise, breach, or identified actor.

## Architecture flow

```text
Synthetic Normal Runs
        ↓
Feature Pipeline
        ↓
Isolation Forest Training
        ↓
Normal Validation Calibration
        ↓
Persisted Model Artifact
        ↓
Offline Run Scoring
        ↓
Anomaly Assessments
        ↓
Synthetic Evaluation
```

## Why IsolationForest

IsolationForest is appropriate for this phase because it learns without attack labels, handles mixed one-hot and numerical feature vectors, is deterministic with a fixed `random_state`, and produces a ranking useful for detecting unusual synthetic behaviour. The model is not trained to recognise attacks and its decision function is not a probability.

## Reproducible dataset construction

The dataset service generates multiple in-memory `normal-operations` runs using configurable, inclusive training and validation seed ranges. Start dates and office-hour start times vary deterministically by seed. Training and validation are split by simulation run, never by event, preventing events from the same run appearing in both sets. Credential-compromise data is prohibited from fitting and calibration.

Defaults are training seeds 1–20, validation seeds 21–30, evaluation seeds 31–40, model `random_state` 42, and target normal false-positive rate 0.02. Seed ranges must be disjoint. Configuration, generated run identities, and permitted event fields produce a stable SHA-256 dataset fingerprint. Training data remains isolated behind the dataset service and is not inserted into the operational run tables.

## Feature schema `synthetic-behaviour-v1`

Included features are:

- cyclical UTC hour (`hour_sin`, `hour_cos`);
- failed-attempt count and `log1p(bytes_transferred)`;
- explicitly encoded privilege level, source/destination asset type, event type, action, and outcome;
- learned source, destination, user, and device identifier frequencies;
- whether a device was unseen earlier in its synthetic run;
- whether the source-to-destination relationship exists in the synthetic inventory.

Missing optional identifiers and privilege values use explicit `missing` categories. Unknown assets use an `unknown` category.

Excluded leakage fields are scenario ID/name, simulation run ID, event ID, synthetic flag, raw database keys, generator severity, evaluation or attack labels, confirmed verdicts, model-generated values, future MITRE mappings, and future incident IDs. Severity is deliberately excluded because it reflects scenario-author intent.

## Calibration and score interpretation

IsolationForest `decision_function` values are stored unchanged as `raw_score`; higher raw values are more normal. Calibration reverses that orientation and builds an empirical cumulative distribution from only training and held-out normal-validation anomaly values. The normalised score is the empirical rank from 0 to 1, with higher values more unusual.

The decision threshold is selected at the `1 - target_false_positive_rate` percentile of held-out normal validation values using a deterministic higher-order statistic, then converted through the same empirical calibration. `calibration_version` is `empirical-normal-cdf-v1`. The score is a relative rank, not a probability of attack or compromise. Finite samples and tied scores can make observed false-positive rates differ slightly from the target.

## Contributing signals

Assessments include up to four transparent signals derived from baseline statistics and inventory checks: failed attempts outside the learned range, transfer volume above normal p99, unseen devices, unusual hours, unexpected relationships, and unseen categorical values. They are contextual contributing signals, not exact IsolationForest feature attribution and not proof of malicious activity. No LLM generates them.

## Artifacts and persistence

Artifacts contain the fitted `DictVectorizer`/IsolationForest pipeline, frequency and numerical baselines, empirical calibration reference, threshold, and schema versions. `MODEL_ARTIFACT_DIR` defaults to `backend/artifacts/models`; `.joblib` files and local databases are ignored by Git. Tests use temporary databases and artifact directories.

Migration `20260721_0003` adds:

- `detection_models` for configuration, fingerprints, calibration, counts, and artifact identity;
- `anomaly_assessments` with a unique `(model_id, event_id)` constraint for idempotent scoring;
- `model_evaluations` for confusion counts, metrics, and baseline comparison.

All rows carry `synthetic: true`.

## Evaluation methodology

Evaluation scores held-out normal-operation and credential-compromise runs before scenario identity is introduced as an evaluation label. It reports confusion counts, precision, recall, F1, false-positive rate, ROC-AUC, average precision, event-level detection coverage, normal events incorrectly flagged, and suspicious-scenario events flagged. The evaluation range is not used to fit or calibrate the model.

The comparison baseline flags events when any documented rule applies: failed attempts ≥ 5, transfer volume above learned normal p99, or non-standard privilege outside 07:00–19:00 UTC. It is transparent and persisted for comparison; it does not replace IsolationForest.

## REST workflow

```text
POST /api/v1/detection/models/train
GET  /api/v1/detection/models
GET  /api/v1/detection/models/{model_id}
POST /api/v1/detection/runs/{run_id}/score
GET  /api/v1/detection/runs/{run_id}/assessments
POST /api/v1/detection/models/{model_id}/evaluate
GET  /api/v1/detection/evaluations/{evaluation_id}
```

Example training request:

```json
{
  "training_seed_range": { "start": 1, "end": 20 },
  "validation_seed_range": { "start": 21, "end": 30 },
  "evaluation_seed_range": { "start": 31, "end": 40 },
  "random_state": 42,
  "target_false_positive_rate": 0.02
}
```

Example scoring request:

```json
{ "model_id": "<synthetic-model-id>", "force_rescore": false }
```

Assessment queries support `page`, `page_size`, `classification`, `minimum_anomaly_score`, `event_type`, `source_id`, `user_id`, and optional `model_id`.

## Current limitations

The synthetic scenarios are deliberately small and structured, so metrics demonstrate engineering reproducibility rather than production detection quality. Calibration is empirical and may be coarse with ties. Artifacts are local filesystem files, model training is synchronous, and SQLite remains single-process oriented. Phase 4A does not stream anomaly assessments over WebSocket, correlate incidents, map MITRE techniques, predict attacks, operate agents, render React Flow topology, use LLM/RAG features, or perform response actions.

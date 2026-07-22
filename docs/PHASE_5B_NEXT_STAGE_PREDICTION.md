# Phase 5B: Next-Stage Prediction

AegisTwin now produces auditable, causal next-stage hypotheses for persisted synthetic simulation runs. The predictor uses only telemetry, anomaly assessments, technique observations, incident snapshots, and infrastructure relationships available at or before each sequence. It never consumes the scenario identifier, scenario name, future events, or evaluation truth as predictive features.

## Pipeline

1. Create a deterministic synthetic run.
2. Score every event with a persisted detection model.
3. Correlate observations into a cautious incident candidate.
4. Persist one prediction snapshot per event sequence.
5. Optionally replay snapshots after the matching correlation update.
6. Evaluate the staged demonstration against a separate evaluation-only truth manifest.

The catalogue is versioned as `aegistwin-progression-v1`; the predictor is `hybrid-progression-v1`. Component scores cover transition, tactic progression, infrastructure reachability, anomaly context, incident coherence, prerequisites, and an explicit contradiction penalty. Scores are ranking aids, not calibrated probabilities.

## API and playback

- `POST /api/v1/prediction/runs/{run_id}/analyze`
- `GET /api/v1/prediction/runs/{run_id}/snapshots?model_id=...`
- `GET /api/v1/prediction/runs/{run_id}/latest?model_id=...`
- `GET /api/v1/prediction/snapshots/{snapshot_id}`
- `GET /api/v1/prediction/snapshots/{snapshot_id}/hypotheses`
- `POST /api/v1/prediction/runs/{run_id}/evaluate`
- `GET /api/v1/prediction/evaluations/{evaluation_id}`

WebSocket playback accepts `prediction_enabled: true` only with detection and correlation enabled. It emits `prediction_ready`, then `next_stage_prediction` after the corresponding incident update. Failures use `prediction_warning` or `prediction_error` with a continue-without-prediction path.

## Evaluation and safety limits

Evaluation uses a small frozen manifest for `staged-compromise-demo` and reports technique, tactic, asset, objective, coverage, reciprocal-rank, and lead-time metrics beside a simple local baseline. This measures one synthetic demonstration only and is not evidence of production or real-world performance.

No external telemetry, live targets, credentials, operational commands, or external runtime intelligence are used. Predictions remain ranked hypotheses about a synthetic world and must not be presented as certainty or confirmed attacks.

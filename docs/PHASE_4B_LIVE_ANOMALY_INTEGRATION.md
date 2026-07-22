# Phase 4B: Live Synthetic Anomaly Integration

Phase 4B presents persisted, offline anomaly assessments beside matching synthetic telemetry. An anomaly means deviation from the synthetic normal baseline; it is not proof of an attack and no score is an attack probability.

## Architecture and scoring boundary

```text
Synthetic Simulation Run
        ↓
Detection Model Selection
        ↓
Offline Causal Run Scoring
        ↓
Persisted Assessments
        ↓
Run-Scoped Playback WebSocket
        ↓
Telemetry Event
        ↓
Matching Anomaly Assessment
        ↓
Live Dashboard
```

The browser creates a run, selects a model returned by `GET /api/v1/detection/models`, and calls `POST /api/v1/detection/runs/{run_id}/score` before opening playback. Persisting all assessments first makes results reproducible, queryable, and auditable. The WebSocket never creates another detector or rescores events.

## Optional WebSocket contract

The original `{ "message_type": "start" }` remains telemetry-only. Detection mode adds `detection_enabled: true` and `model_id`. The server verifies the synthetic model and artifact and requires exactly one persisted assessment for every event. It sends `detection_ready`, then `playback_started`, followed by a `telemetry_event` and its `anomaly_assessment` for each event. `detection_warning` reports incomplete assessments and `detection_error` reports model/artifact failures. Both allow retry or an explicit telemetry-only fallback.

All messages retain `message_type`, `run_id`, envelope `sequence_number`, `server_timestamp`, `synthetic: true`, and `payload`. Assessment payloads include event sequence, model/schema/calibration identity, raw Isolation Forest score, rank, hybrid score, threshold, normal/anomalous classification, contributing signals, and component scores. Event identity and sequence—not array position—join the message types.

Pause gates both streams. Stop cancels further messages. Completion follows the final assessment. `after_sequence=N` skips event/assessment pairs through N. The initial snapshot states detection is disabled until the optional start control selects a model; `detection_ready` reports the selected model, scoring completeness, and resume offset. A snapshot never exposes future assessments.

## Dashboard and analytics

The playback provider owns model loading, scoring status, selected model, assessment map, ordered timeline, current assessment, and detection failure state. It clears assessments between runs and closes its socket on unmount. Malformed assessment envelopes fail runtime validation without crashing the UI.

The overview provides model controls, current assessment, contributing signals, component progress bars, a Recharts timeline sourced only from streamed values, factual playback totals, and assessment state on each original telemetry row. Component values describe deviation contributions, not probabilities. Model Analytics lists model provenance, trains deterministic normal-only synthetic models, and evaluates selected models with a synthetic-benchmark disclaimer.

## Model cache

Artifacts use a thread-safe process-local cache keyed by resolved artifact path and file modification time. An unchanged artifact is reused; replacement invalidates it on the next load, and tests clear the cache around each case. Missing or invalid artifacts produce a structured error. The cache is not shared across workers or hosts and is not a distributed consistency mechanism.

## Safety, fallback, and limitations

Only repository-generated synthetic telemetry is accepted. There are no external connections, real security logs, scans, authentication attempts, containment actions, incident correlation, MITRE mapping, attack-stage prediction, agents, LLM/RAG, or response orchestration. A scoring failure preserves the run and existing assessments. Users may retry a forced rescore or continue telemetry-only. Storage and artifact caching remain local and single-process.
